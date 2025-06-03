import os

import psycopg
import pytest
from psycopg.rows import namedtuple_row

from db.tests.conftest import detailed_notice_handler


def db_url(user: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/test"


@pytest.mark.skipif(
    os.getenv("PG_MAJOR") == "15", reason="extension does not support pg15"
)
def test_same_table_vectorizer_timescaledb():
    with psycopg.connect(
        db_url("postgres"), autocommit=True, row_factory=namedtuple_row
    ) as con:
        with con.cursor() as cur:
            cur.execute("create extension if not exists timescaledb")
            cur.execute("select to_regrole('bob') is null")
            if cur.fetchone()[0] is True:
                cur.execute("create user bob")
            cur.execute("select to_regrole('adelaide') is null")
            if cur.fetchone()[0] is True:
                cur.execute("create user adelaide")
            cur.execute("create extension if not exists ai cascade")
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
                , drop_me text
                , primary key (title, published)
                )
            """)
            cur.execute(
                """grant select, insert, update, delete on website.blog to bob, adelaide"""
            )
            cur.execute("""grant usage on schema website to adelaide""")
            cur.execute("""
                insert into website.blog(title, published, body)
                values
                  ('how to cook a hot dog', '2024-01-06'::timestamptz, 'put it on a hot grill')
                , ('how to make a sandwich', '2023-01-06'::timestamptz, 'put a slice of meat between two pieces of bread')
                , ('how to make stir fry', '2022-01-06'::timestamptz, 'pick up the phone and order takeout')
            """)

            # drop the drop_me column
            cur.execute("alter table website.blog drop column drop_me")

            # create a vectorizer for the blog table
            # language=PostgreSQL
            cur.execute("""
            select ai.create_vectorizer
            ( 'website.blog'::regclass
            , loading=>ai.loading_column('body')
            , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
            , formatting=>ai.formatting_python_template('title: $title published: $published $chunk')
            , scheduling=>ai.scheduling_timescaledb
                    ( interval '5m'
                    , initial_start=>'2050-01-06'::timestamptz
                    , timezone=>'America/Chicago'
                    )
            , destination=>ai.destination_column('embedding1')
            , chunking=>ai.chunking_none()
            );
            """)
            vectorizer_id = cur.fetchone()[0]

            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer_id,))
            actual = cur.fetchone()[0]
            assert actual == 3

            cur.execute(
                """
                select (x.config->'scheduling'->>'job_id')::int 
                from ai.vectorizer x 
                where x.id = %s
                """,
                (vectorizer_id,),
            )
            job_id = cur.fetchone()[0]

            cur.execute("call public.run_job(%s)", (job_id,))

            # check that the queue has 0 rows
            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer_id,))
            actual = cur.fetchone()[0]
            assert actual == 0

            # assert website table has embedding column
            cur.execute(
                "select column_name from information_schema.columns where table_name = 'blog'"
            )
            columns = [row[0] for row in cur.fetchall()]
            assert "embedding1" in columns

            # edit website rows
            cur.execute("""
                update website.blog
                set title = 'how to cook a cold dog'
                where title = 'how to cook a hot dog'
            """)

            # check that the queue has 0 rows
            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer_id,))
            actual = cur.fetchone()[0]
            assert actual == 1

            cur.execute("call public.run_job(%s)", (job_id,))
            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer_id,))
            actual = cur.fetchone()[0]
            assert actual == 0

            # edit the embedding column with a vector
            cur.execute("""
                update website.blog
                set embedding1 = array_fill(0.1::float8, ARRAY[768])::vector
                where title = 'how to cook a cold dog'
            """)

            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer_id,))
            actual = cur.fetchone()[0]
            assert actual == 0

            # Create a second vectorizer

            cur.execute("""
                select ai.create_vectorizer
                ( 'website.blog'::regclass
                , loading=>ai.loading_column('body')
                , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
                , formatting=>ai.formatting_python_template('title: $title published: $published $chunk')
                , scheduling=>ai.scheduling_timescaledb
                        ( interval '5m'
                        , initial_start=>'2050-01-06'::timestamptz
                        , timezone=>'America/Chicago'
                        )
                , destination=>ai.destination_column('embedding2')
                , chunking=>ai.chunking_none()
                );
                """)
            vectorizer2_id = cur.fetchone()[0]

            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer2_id,))
            actual = cur.fetchone()[0]
            assert actual == 3

            cur.execute(
                """
                select (x.config->'scheduling'->>'job_id')::int 
                from ai.vectorizer x 
                where x.id = %s
                """,
                (vectorizer2_id,),
            )
            job2_id = cur.fetchone()[0]

            cur.execute("call public.run_job(%s)", (job2_id,))

            # check that the queue has 0 rows
            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer2_id,))
            actual = cur.fetchone()[0]
            assert actual == 0

            # assert website table has embedding2 column
            cur.execute(
                "select column_name from information_schema.columns where table_name = 'blog'"
            )
            columns = [row[0] for row in cur.fetchall()]
            assert "embedding2" in columns

            # edit website rows
            cur.execute("""
                update website.blog
                set title = 'how to cook a warm dog'
                where title = 'how to cook a cold dog'
            """)

            # check that both queues have 1 row
            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer2_id,))
            actual = cur.fetchone()[0]
            assert actual == 1

            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer_id,))
            actual = cur.fetchone()[0]
            assert actual == 1

            cur.execute("call public.run_job(%s)", (job2_id,))
            cur.execute("call public.run_job(%s)", (job_id,))

            # edit the embedding columns
            cur.execute("""
                update website.blog
                set embedding1 = array_fill(0.2::float8, ARRAY[768])::vector
                where title = 'how to cook a warm dog'
            """)

            cur.execute("""
                update website.blog
                set embedding2 = array_fill(0.3::float8, ARRAY[768])::vector
                where title = 'how to cook a warm dog'
            """)

            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer2_id,))
            actual = cur.fetchone()[0]
            assert actual == 0

            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer_id,))
            actual = cur.fetchone()[0]
            assert actual == 0

            # Create a third non-same-table vectorizer

            cur.execute("""
                           select ai.create_vectorizer
                           ( 'website.blog'::regclass
                           , loading=>ai.loading_column('body')
                           , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
                           , formatting=>ai.formatting_python_template('title: $title published: $published $chunk')
                           , scheduling=>ai.scheduling_timescaledb
                                   ( interval '5m'
                                   , initial_start=>'2050-01-06'::timestamptz
                                   , timezone=>'America/Chicago'
                                   )
                           );
                           """)

            vectorizer3_id = cur.fetchone()[0]

            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer3_id,))
            actual = cur.fetchone()[0]
            assert actual == 3

            cur.execute(
                """
                select (x.config->'scheduling'->>'job_id')::int 
                from ai.vectorizer x 
                where x.id = %s
                """,
                (vectorizer3_id,),
            )
            job3_id = cur.fetchone()[0]

            cur.execute("call public.run_job(%s)", (job3_id,))

            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer3_id,))
            actual = cur.fetchone()[0]
            assert actual == 0

            cur.execute("""
                            update website.blog
                            set title = 'how to cook a spicy dog'
                            where title = 'how to cook a warm dog'
                        """)

            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer_id,))
            actual = cur.fetchone()[0]
            assert actual == 1

            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer2_id,))
            actual = cur.fetchone()[0]
            assert actual == 1

            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer3_id,))
            actual = cur.fetchone()[0]
            assert actual == 1

            cur.execute("call public.run_job(%s)", (job_id,))
            cur.execute("call public.run_job(%s)", (job2_id,))
            cur.execute("call public.run_job(%s)", (job3_id,))

            cur.execute("""
                            update website.blog
                            set embedding1 = array_fill(0.2::float8, ARRAY[768])::vector
                            where title = 'how to make a sandwich'
                        """)

            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer_id,))
            actual = cur.fetchone()[0]
            assert actual == 0

            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer2_id,))
            actual = cur.fetchone()[0]
            assert actual == 0

            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer3_id,))
            actual = cur.fetchone()[0]
            assert actual == 0

            # Do an insert
            cur.execute("""
                insert into website.blog(title, published, body)
                values
                  ('how to cook spaghetti', '2024-01-06'::timestamptz, 'put it on a hot grill')
            """)

            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer_id,))
            actual = cur.fetchone()[0]
            assert actual == 1

            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer2_id,))
            actual = cur.fetchone()[0]
            assert actual == 1

            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer3_id,))
            actual = cur.fetchone()[0]
            assert actual == 1

            # Do a delete
            cur.execute("""
                delete from website.blog
                where title = 'how to cook spaghetti'
            """)
