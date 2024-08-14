import os
import subprocess

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
                "provider": "openai",
                "model": "text-embedding-3-small",
            },
        ),
        (
            "select ai.embedding_config_openai('text-embedding-3-small', _dimensions=>128)",
            {
                "provider": "openai",
                "model": "text-embedding-3-small",
                "dimensions": 128,
            },
        ),
        (
            "select ai.embedding_config_openai('text-embedding-3-small', _dimensions=>128, _user=>'bob')",
            {
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
            , 'size: $size shape: $shape $chunk$'
            )
            """,
            {
                "implementation": "python_string_template",
                "columns": ["size", "shape"],
                "template": "size: $size shape: $shape $chunk",
            },
        ),
        (
            """
            select ai.formatting_config_python_string_template
            ( array['color', 'weight', 'category']
            , 'color: $color weight: $weight category: $category $chunk'
            )
            """,
            {
                "implementation": "python_string_template",
                "columns": ["color", "weight", "category"],
                "template": "color: $color weight: $weight category: $category $chunk",
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


SOURCE_TABLE = """
                                                               Table "website.blog"
  Column   |           Type           | Collation | Nullable |           Default            | Storage  | Compression | Stats target | Description 
-----------+--------------------------+-----------+----------+------------------------------+----------+-------------+--------------+-------------
 id        | integer                  |           | not null | generated always as identity | plain    |             |              | 
 title     | text                     |           | not null |                              | extended |             |              | 
 published | timestamp with time zone |           | not null |                              | plain    |             |              | 
 body      | text                     |           | not null |                              | extended |             |              | 
Indexes:
    "blog_pkey" PRIMARY KEY, btree (title, published)
Referenced by:
    TABLE "website.blog_embedding" CONSTRAINT "blog_embedding_title_published_fkey" FOREIGN KEY (title, published) REFERENCES website.blog(title, published) ON DELETE CASCADE
Triggers:
    vectorizer_trg_1 AFTER INSERT OR DELETE OR UPDATE ON website.blog FOR EACH ROW EXECUTE FUNCTION ai.vectorizer_trg_1()
Access method: heap
""".strip()


TARGET_TABLE = """
                                                    Table "website.blog_embedding"
  Column   |           Type           | Collation | Nullable |      Default      | Storage  | Compression | Stats target | Description 
-----------+--------------------------+-----------+----------+-------------------+----------+-------------+--------------+-------------
 id        | uuid                     |           | not null | gen_random_uuid() | plain    |             |              | 
 title     | text                     |           | not null |                   | extended |             |              | 
 published | timestamp with time zone |           | not null |                   | plain    |             |              | 
 chunk_seq | integer                  |           | not null |                   | plain    |             |              | 
 chunk     | text                     |           | not null |                   | extended |             |              | 
 embedding | vector(768)              |           | not null |                   | external |             |              | 
Indexes:
    "blog_embedding_pkey" PRIMARY KEY, btree (id)
    "blog_embedding_title_published_chunk_seq_key" UNIQUE CONSTRAINT, btree (title, published, chunk_seq)
Foreign-key constraints:
    "blog_embedding_title_published_fkey" FOREIGN KEY (title, published) REFERENCES website.blog(title, published) ON DELETE CASCADE
Access method: heap
""".strip()


QUEUE_TABLE = """
                                                  Table "ai.vectorizer_q_1"
  Column   |           Type           | Collation | Nullable | Default | Storage  | Compression | Stats target | Description 
-----------+--------------------------+-----------+----------+---------+----------+-------------+--------------+-------------
 title     | text                     |           | not null |         | extended |             |              | 
 published | timestamp with time zone |           | not null |         | plain    |             |              | 
 queued_at | timestamp with time zone |           | not null | now()   | plain    |             |              | 
Indexes:
    "vectorizer_q_1_title_published_idx" btree (title, published)
Triggers:
    vectorizer_q_1 AFTER INSERT ON ai.vectorizer_q_1 FOR EACH STATEMENT EXECUTE FUNCTION ai.vectorizer_q_1()
Access method: heap
""".strip()


def test_vectorizer():
    with psycopg.connect(db_url("postgres"), autocommit=True, row_factory=namedtuple_row) as con:
        with con.cursor() as cur:
            drop_website_schema(cur)
            create_website_schema(cur)
            drop_blog_table(cur)
            create_blog_table(cur)

            # create a vectorizer for the blog table
            cur.execute("""
            select ai.create_vectorizer
            ( 'website.blog'::regclass
            , 768
            , _embedding=>ai.embedding_config_openai('text-embedding-3-small', _dimensions=>768)
            , _chunking=>ai.chunking_config_token_text_splitter('body', 128, 10)
            , _formatting=>ai.formatting_config_python_string_template
                    ( array['title', 'published']
                    , 'title: $title published: $published $chunk'
                    )
            );
            """)
            vectorizer_id = cur.fetchone()[0]

            # check the config that was created
            cur.execute("select * from ai.vectorizer where id = %s", (vectorizer_id,))
            row = cur.fetchone()
            assert row.id == vectorizer_id
            assert row.asynchronous is True
            assert row.external is True
            assert row.source_schema == "website"
            assert row.source_table == "blog"
            assert len(row.source_pk) == 2
            assert row.target_schema == "website"
            assert row.target_table == "blog_embedding"
            assert "embedding" in row.config
            assert "chunking" in row.config
            assert "formatting" in row.config

            # check the request
            cur.execute("select count(*) from ai.vectorizer_request where vectorizer_id = %s", (vectorizer_id,))
            assert cur.fetchone()[0] == 1

            # execute the vectorizer
            cur.execute("select ai.execute_vectorizer(%s)", (vectorizer_id,))

            # check that we don't schedule a second request when one is pending
            cur.execute("select count(*) from ai.vectorizer_request where vectorizer_id = %s", (vectorizer_id,))
            assert cur.fetchone()[0] == 1

            # pretend we are working it
            cur.execute("update ai.vectorizer_request set status = 'running', started = now() where vectorizer_id = %s", (vectorizer_id,))

            # execute the vectorizer
            cur.execute("select ai.execute_vectorizer(%s)", (vectorizer_id,))

            # check that we don't schedule a second request when one is running
            cur.execute("select count(*) from ai.vectorizer_request where vectorizer_id = %s", (vectorizer_id,))
            assert cur.fetchone()[0] == 1

            # forcefully execute the vectorizer
            cur.execute("select ai.execute_vectorizer(%s, _force=>true)", (vectorizer_id,))

            # check the request
            cur.execute("select count(*) from ai.vectorizer_request where vectorizer_id = %s", (vectorizer_id,))
            assert cur.fetchone()[0] == 2

            # delete the requests
            cur.execute("delete from ai.vectorizer_request where vectorizer_id = %s", (vectorizer_id,))

            # execute the vectorizer
            cur.execute("select ai.execute_vectorizer(%s)", (vectorizer_id,))

            # check that we have one request
            cur.execute("select count(*) from ai.vectorizer_request where vectorizer_id = %s", (vectorizer_id,))
            assert cur.fetchone()[0] == 1

    # does the source table look right?
    cmd = f'''psql -X -d "{db_url('test')}" -c "\d+ website.blog"'''
    proc = subprocess.run(cmd, shell=True, check=True, text=True, capture_output=True)
    actual = str(proc.stdout).strip()
    assert actual == SOURCE_TABLE

    # does the target table look right?
    cmd = f'''psql -X -d "{db_url('test')}" -c "\d+ website.blog_embedding"'''
    proc = subprocess.run(cmd, shell=True, check=True, text=True, capture_output=True)
    actual = str(proc.stdout).strip()
    assert actual == TARGET_TABLE

    # does the queue table look right?
    cmd = f'''psql -X -d "{db_url('test')}" -c "\d+ ai.vectorizer_q_1"'''
    proc = subprocess.run(cmd, shell=True, check=True, text=True, capture_output=True)
    actual = str(proc.stdout).strip()
    assert actual == QUEUE_TABLE

