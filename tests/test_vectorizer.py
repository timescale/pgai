import os

import psycopg
import pytest


# skip tests in this module if disabled
enable_vectorize_tests = os.getenv("ENABLE_VECTORIZE_TESTS")
if not enable_vectorize_tests or enable_vectorize_tests == "0":
    pytest.skip(allow_module_level=True)


def cur(user: str) -> psycopg.Cursor:
    with psycopg.connect(f"postgres://{user}@127.0.0.1:5432/test") as con:
        with con.cursor() as cur:
            yield cur


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


def test_vectorize(cur):
    drop_website_schema(cur)
    create_website_schema(cur)
    drop_blog_table(cur)
    create_blog_table(cur)
    cur.execute("""
    select ai.vectorize_async
    ( 'website.blog'::regclass
    , 768
    , '{}'::jsonb
    );
    """)
    id = cur.fetchone()[0]
    cur.execute("""
    select * from ai.vectorize
    where id = %s
    """, (id,))
    row = cur.fetchone()
    assert row.id == id
    assert row.source_schema == "website"
    assert row.source_table == "blog"
    assert row.target_schema == "website"
    assert row.target_table == "blog_embedding"
    assert row.queue_schema == "website"
    assert row.queue_table == "blog_embedding_q"


def test_vectorize2(cur):
    drop_website_schema(cur)
    create_website_schema(cur)
    drop_blog_table(cur)
    create_blog_table(cur)
    cur.execute("""
    select ai.vectorize_async
    ( 'website.blog'::regclass
    , 768
    , '{}'::jsonb
    , _target_table=>'blog_target'
    );
    """)
    id = cur.fetchone()[0]
    cur.execute("""
    select * from ai.vectorize
    where id = %s
    """, (id,))
    row = cur.fetchone()
    assert row.id == id
    assert row.source_schema == "website"
    assert row.source_table == "blog"
    assert row.target_schema == "website"
    assert row.target_table == "blog_target"
    assert row.queue_schema == "website"
    assert row.queue_table == "blog_target_q"
