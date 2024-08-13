import os

import psycopg
from psycopg.rows import namedtuple_row
import pytest

# skip tests in this module if disabled
enable_vectorize_tests = os.getenv("ENABLE_VECTORIZE_TESTS")
if not enable_vectorize_tests or enable_vectorize_tests == "0":
    pytest.skip(allow_module_level=True)


def db_url(user: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/test"


def test_embedding_config_openai():
    tests = [
        (
            "select ai.embedding_config_openai('text-embedding-3-small')",
            {
                "version": "0.4.0",
                "provider": "openai",
                "model": "text-embedding-3-small",
            },
        ),
        (
            "select ai.embedding_config_openai('text-embedding-3-small', _dimensions=>128)",
            {
                "version": "0.4.0",
                "provider": "openai",
                "model": "text-embedding-3-small",
                "dimensions": 128,
            },
        ),
        (
            "select ai.embedding_config_openai('text-embedding-3-small', _dimensions=>128, _user=>'bob')",
            {
                "version": "0.4.0",
                "provider": "openai",
                "model": "text-embedding-3-small",
                "dimensions": 128,
                "user": "bob",
            },
        ),
    ]
    with psycopg.connect(db_url("test")) as con:
        with con.cursor() as cur:
            for query, expected in tests:
                cur.execute(query)
                actual = cur.fetchone()[0]
                assert actual.keys() == expected.keys()
                for k, v in actual.items():
                    assert k in expected and v == expected[k]


def test_chunking_config_token_text_splitter():
    tests = [
        (
            "select ai.chunking_config_token_text_splitter('body', 128, 10)",
            {
                "version": "0.4.0",
                "separator": " ",
                "chunk_size": 128,
                "chunk_column": "body",
                "chunk_overlap": 10,
                "implementation": "token_text_splitter",
            },
        ),
        (
            "select ai.chunking_config_token_text_splitter('content', 256, 20, _separator=>E'\n')",
            {
                "version": "0.4.0",
                "separator": "\n",
                "chunk_size": 256,
                "chunk_column": "content",
                "chunk_overlap": 20,
                "implementation": "token_text_splitter",
            },
        ),
    ]
    with psycopg.connect(db_url("test")) as con:
        with con.cursor() as cur:
            for query, expected in tests:
                cur.execute(query)
                actual = cur.fetchone()[0]
                assert actual.keys() == expected.keys()
                for k, v in actual.items():
                    assert k in expected and v == expected[k]


def test_formatting_config_python_string_template():
    tests = [
        (
            """
            select ai.formatting_config_python_string_template
            ( array['size', 'shape']
            , $tmpl$size: $size shape: $shape $chunk$tmpl$
            )
            """,
            {
                "version": "0.4.0",
                "implementation": "python_string_template",
                "columns": ["size", "shape"],
                "template": "size: $size shape: $shape $chunk",
            },
        ),
        (
            """
            select ai.formatting_config_python_string_template
            ( array['color', 'weight', 'category']
            , $tmpl$color: $color weight: $weight category: $category $chunk $tmpl$
            )
            """,
            {
                "version": "0.4.0",
                "implementation": "python_string_template",
                "columns": ["color", "weight", "category"],
                "template": "color: $color weight: $weight category: $category $chunk ",
            },
        ),
    ]
    with psycopg.connect(db_url("test")) as con:
        with con.cursor() as cur:
            for query, expected in tests:
                cur.execute(query)
                actual = cur.fetchone()[0]
                assert actual.keys() == expected.keys()
                for k, v in actual.items():
                    assert k in expected and v == expected[k]


def drop_website_schema(cursor: psycopg.Cursor) -> None:
    cursor.execute("drop schema if exists website cascade")


def create_website_schema(cursor: psycopg.Cursor) -> None:
    cursor.execute("create schema website")


def drop_blog_table(cursor: psycopg.Cursor) -> None:
    cursor.execute("drop table if exists website.blog")


def create_blog_table(cursor: psycopg.Cursor) -> None:
    cursor.execute("""
    create table website.blog
    ( id int not null generated always as identity
    , title text not null
    , published timestamptz
    , body text not null
    , primary key (title, published)
    )
    """)


def test_create_async_vectorizer():
    with psycopg.connect(db_url("postgres")) as con:
        with con.cursor() as cur:
            drop_website_schema(cur)
            create_website_schema(cur)
            cur.execute("grant all privileges on schema website to test")
            cur.execute("grant all privileges on ai.vectorizer_config to test")  # TODO: remove once privileges sorted
            cur.execute("grant all privileges on ai.vectorizer_execution to test")  # TODO: remove once privileges sorted
    with psycopg.connect(db_url("test"), row_factory=namedtuple_row) as con:
        with con.cursor() as cur:
            # create a table to vectorizer
            drop_blog_table(cur)
            create_blog_table(cur)

            # create a vectorizer for the blog table
            cur.execute("""
            select ai.create_async_vectorizer
            ( 'website.blog'::regclass
            , 768
            , _embedding=>ai.embedding_config_openai('text-embedding-3-small', _dimensions=>768)
            , _chunking=>ai.chunking_config_token_text_splitter('body', 128, 10)
            , _formatting=>ai.formatting_config_python_string_template
                    ( array['title', 'published']
                    , $tmpl$title: $title published: $published $chunk $tmpl$
                    )
            );
            """)
            id = cur.fetchone()[0]
            con.commit()

            # check the config that was created
            cur.execute("select * from ai.vectorizer_config where id = %s", (id,))
            row = cur.fetchone()
            assert row.id == id
            assert row.source_schema == "website"
            assert row.source_table == "blog"
            assert row.target_schema == "website"
            assert row.target_table == "blog_embedding"
            assert row.queue_schema == "website"
            assert row.queue_table == "blog_embedding_q"
            assert "embedding" in row.config
            assert "chunking" in row.config
            assert "formatting" in row.config

            # execute the vectorizer
            cur.execute("select ai.execute_vectorizer(%s)", (id,))
            con.commit()

            # check the execution
            cur.execute("select count(*) from ai.vectorizer_execution where config_id = %s", (id,))
            assert cur.fetchone()[0] == 1

