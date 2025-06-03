import os

import psycopg
import pytest
from psycopg.rows import namedtuple_row

from db.tests.conftest import detailed_notice_handler


def db_url(user: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/test"


def setup_website_blog_table():
    with psycopg.connect(
        db_url("test"), autocommit=True, row_factory=namedtuple_row
    ) as con:
        con.add_notice_handler(detailed_notice_handler)
        with con.cursor() as cur:
            cur.execute("drop schema if exists website cascade")
            cur.execute("create schema website")
            cur.execute("drop table if exists website.blog")
            cur.execute("""
                create table website.blog
                ( id int not null generated always as identity
                , title text not null
                , published timestamptz
                , body text not null
                , primary key (title, published)
                )
            """)
            cur.execute("""
                insert into website.blog(title, published, body)
                values
                  ('how to cook a hot dog', '2024-01-06'::timestamptz, 'put it on a hot grill')
                , ('how to make a sandwich', '2023-01-06'::timestamptz, 'put a slice of meat between two pieces of bread')
                , ('how to make stir fry', '2022-01-06'::timestamptz, 'pick up the phone and order takeout')
            """)


@pytest.mark.skipif(
    os.getenv("PG_MAJOR") == "15", reason="extension does not support pg15"
)
def test_named_vectorizer_timescaledb():
    setup_website_blog_table()
    with psycopg.connect(
        db_url("test"), autocommit=True, row_factory=namedtuple_row
    ) as con:
        con.add_notice_handler(detailed_notice_handler)
        with con.cursor() as cur:
            # create a vectorizer for the blog table
            # language=PostgreSQL
            cur.execute("""
                select ai.create_vectorizer
                ( 'website.blog'::regclass
                , name => 'blog_vectorizer'
                , loading=>ai.loading_column('body')
                , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
                , formatting=>ai.formatting_python_template('title: $title published: $published $chunk')
                , scheduling=>ai.scheduling_none()
                , destination=>ai.destination_column('embedding1')
                , chunking=>ai.chunking_none()
                );
                """)

            cur.execute("create extension ai cascade")
            cur.execute(
                "select set_config('ai.external_functions_executor_url', 'http://0.0.0.0:8000', false)"
            )
            cur.execute(
                "select set_config('ai.external_functions_executor_events_path', '/api/v1/events', false)"
            )
            cur.execute("select ai.execute_vectorizer('blog_vectorizer')")

            with pytest.raises(psycopg.errors.NoDataFound):
                cur.execute("select ai.execute_vectorizer('non_existent_vectorizer')")


def test_named_vectorizer():
    setup_website_blog_table()
    with psycopg.connect(
        db_url("test"), autocommit=True, row_factory=namedtuple_row
    ) as con:
        con.add_notice_handler(detailed_notice_handler)
        with con.cursor() as cur:
            # create a vectorizer for the blog table
            # language=PostgreSQL
            cur.execute("""
            select ai.create_vectorizer
            ( 'website.blog'::regclass
            , name => 'blog_vectorizer'
            , loading=>ai.loading_column('body')
            , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
            , formatting=>ai.formatting_python_template('title: $title published: $published $chunk')
            , scheduling=>ai.scheduling_none()
            , destination=>ai.destination_column('embedding1')
            , chunking=>ai.chunking_none()
            );
            """)

            cur.execute(
                "select ai.vectorizer_queue_pending(name => %s)", ("blog_vectorizer",)
            )
            pending = cur.fetchone()[0]
            assert pending == 3

            # testing ai.vectorizer_status view filtering by vectorizer name
            cur.execute(
                "select pending_items from ai.vectorizer_status where name = %s",
                ("blog_vectorizer",),
            )
            status_pending_items = cur.fetchone()[0]
            assert status_pending_items == 3

            # create another vectorizer with same name but if not exists set
            cur.execute("""
            select ai.create_vectorizer
            ( 'website.blog'::regclass
            , name => 'blog_vectorizer'
            , loading=>ai.loading_column('body')
            , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
            , formatting=>ai.formatting_python_template('title: $title published: $published $chunk')
            , scheduling=>ai.scheduling_none()
            , destination=>ai.destination_column('embedding1')
            , chunking=>ai.chunking_none()
            , if_not_exists => true
            );
            """)

            cur.execute(
                "select ai.vectorizer_queue_pending(name => %s)", ("blog_vectorizer",)
            )
            pending = cur.fetchone()[0]
            assert pending == 3

            with pytest.raises(psycopg.errors.DuplicateObject):
                # create a vectorizer with same name but if not exists set to false
                cur.execute("""
                select ai.create_vectorizer
                ( 'website.blog'::regclass
                , name => 'blog_vectorizer'
                , loading=>ai.loading_column('body')
                , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
                , formatting=>ai.formatting_python_template('title: $title published: $published $chunk')
                , scheduling=>ai.scheduling_none()
                , destination=>ai.destination_column('embedding1')
                , chunking=>ai.chunking_none()
                , if_not_exists => false
                );
                """)

            # create a vectorizer with no name check default name
            cur.execute("""
               select ai.create_vectorizer
               ( 'website.blog'::regclass
               , loading=>ai.loading_column('body')
               , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
               , formatting=>ai.formatting_python_template('title: $title published: $published $chunk')
               , scheduling=>ai.scheduling_none()
               , destination=>ai.destination_column('embedding1')
               , chunking=>ai.chunking_none()
               , if_not_exists => false
               );
               """)

            vectorizer_id_2 = cur.fetchone()[0]
            cur.execute(
                """
                select name from ai.vectorizer where id = %s
            """,
                (vectorizer_id_2,),
            )
            vectorizer_name = cur.fetchone()[0]
            assert vectorizer_name == "website_blog_embedding1"

            # Test fetch errors by vectorizer name
            cur.execute(
                "insert into ai._vectorizer_errors (id, message) values (%s, %s)",
                (vectorizer_id_2, "test error message"),
            )

            cur.execute(
                "select * from ai.vectorizer_errors where name = %s",
                (vectorizer_name,),
            )

            error = cur.fetchone()
            assert error.message == "test error message"

            # create a vectorizer with no name check default name
            cur.execute("""
               select ai.create_vectorizer
               ( 'website.blog'::regclass
               , loading=>ai.loading_column('body')
               , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
               , formatting=>ai.formatting_python_template('title: $title published: $published $chunk')
               , scheduling=>ai.scheduling_none()
               , destination=>ai.destination_table()
               , chunking=>ai.chunking_none()
               , if_not_exists => false
               );
               """)
            vectorizer_id_3 = cur.fetchone()[0]
            cur.execute(
                """
                            select name from ai.vectorizer where id = %s
                        """,
                (vectorizer_id_3,),
            )
            vectorizer_name = cur.fetchone()[0]
            assert vectorizer_name == "website_blog_embedding_store"

            # try to recreate the vectorizer with the same default name
            # and if not exists set to true
            cur.execute("""
               select ai.create_vectorizer
               ( 'website.blog'::regclass
               , loading=>ai.loading_column('body')
               , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
               , formatting=>ai.formatting_python_template('title: $title published: $published $chunk')
               , scheduling=>ai.scheduling_none()
               , destination=>ai.destination_table()
               , chunking=>ai.chunking_none()
               , if_not_exists => true
               );
               """)
            vectorizer_id_3 = cur.fetchone()[0]
            cur.execute(
                """
                            select name from ai.vectorizer where id = %s
                        """,
                (vectorizer_id_3,),
            )
            vectorizer_name = cur.fetchone()[0]
            assert vectorizer_name == "website_blog_embedding_store"

            # make sure their is an error if if_not_exists is false
            with pytest.raises(psycopg.errors.DuplicateObject):
                cur.execute("""
                select ai.create_vectorizer
                ( 'website.blog'::regclass
                , loading=>ai.loading_column('body')
                , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
                , formatting=>ai.formatting_python_template('title: $title published: $published $chunk')
                , scheduling=>ai.scheduling_none()
                , destination=>ai.destination_table()
                , chunking=>ai.chunking_none()
                , if_not_exists => false
                );
                """)

            # test functions with vectorizer name can be called without error
            cur.execute(
                "select ai.disable_vectorizer_schedule(%s)",
                ("website.blog_embedding_store",),
            )
            cur.execute(
                "select ai.enable_vectorizer_schedule(%s)",
                ("website.blog_embedding_store",),
            )
            cur.execute(
                "select ai.vectorizer_queue_pending(%s)",
                ("website.blog_embedding_store",),
            )
            cur.execute(
                "select ai.drop_vectorizer(%s, drop_all => true)",
                ("website.blog_embedding_store",),
            )
