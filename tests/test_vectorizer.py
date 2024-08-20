import os
import subprocess
import json

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


def test_validate_chunking_config_token_text_splitter():
    ok = [
        """
        select ai._validate_chunking_config_token_text_splitter
        ( ai.chunking_config_token_text_splitter('body', 128, 10)
        , 'public', 'thing'
        )
        """,
    ]
    bad = [
        """
        select ai._validate_chunking_config_token_text_splitter
        ( ai.chunking_config_token_text_splitter('content', 128, 10)
        , 'public', 'thing'
        )
        """,
    ]
    with psycopg.connect(db_url("test")) as con:
        with con.cursor() as cur:
            cur.execute("drop table if exists public.thing;")
            cur.execute("create table public.thing (id int, color text, weight float, body text)")
            for query in ok:
                cur.execute(query)
                assert True
            for query in bad:
                with pytest.raises(psycopg.errors.RaiseException):
                    cur.execute(query)
            con.rollback()


def test_scheduling_config_none():
    tests = [
        (
            "select ai.scheduling_config_none()",
            {
                "implementation": "none",
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


def test_scheduling_config_pg_cron():
    tests = [
        (
            "select ai.scheduling_config_pg_cron('*/5 * * * *')",
            {
                "implementation": "pg_cron",
                "schedule": "*/5 * * * *",
            },
        ),
        (
            "select ai.scheduling_config_pg_cron('0 * * * *')",
            {
                "implementation": "pg_cron",
                "schedule": "0 * * * *",
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


def test_scheduling_config_timescaledb():
    tests = [
        (
            "select ai.scheduling_config_timescaledb(interval '5m')",
            {
                "implementation": "timescaledb",
                "schedule_interval": "00:05:00",
            },
        ),
        (
            "select ai.scheduling_config_timescaledb(interval '1h', _timezone=>'America/Chicago')",
            {
                "implementation": "timescaledb",
                "schedule_interval": "01:00:00",
                "timezone": "America/Chicago",
            },
        ),
        (
            "select ai.scheduling_config_timescaledb(interval '10m', _fixed_schedule=>true, _timezone=>'America/Chicago')",
            {
                "implementation": "timescaledb",
                "schedule_interval": "00:10:00",
                "timezone": "America/Chicago",
                "fixed_schedule": True,
            },
        ),
        (
            "select ai.scheduling_config_timescaledb(interval '15m', _initial_start=>'2025-01-06 America/Chicago'::timestamptz, _fixed_schedule=>false, _timezone=>'America/Chicago')",
            {
                "implementation": "timescaledb",
                "schedule_interval": "00:15:00",
                "timezone": "America/Chicago",
                "fixed_schedule": False,
                "initial_start": "2025-01-06T06:00:00+00:00",
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
            , 'size: $size shape: $shape $chunk'
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


def test_validate_formatting_config_python_string_template():
    ok = [
        """
        select ai._validate_formatting_config_python_string_template
        ( ai.formatting_config_python_string_template
          ( array['color', 'weight']
          , 'color: $color weight: $weight $chunk'
          )
        , 'public', 'thing'
        )
        """,
    ]
    bad = [
        """
        select ai._validate_formatting_config_python_string_template
        ( ai.formatting_config_python_string_template
          ( array['color', 'weight', 'height']
          , 'color: $color weight: $weight height: $height $chunk'
          )
        , 'public', 'thing'
        )
        """,
    ]
    with psycopg.connect(db_url("test")) as con:
        with con.cursor() as cur:
            cur.execute("drop table if exists public.thing;")
            cur.execute("create table public.thing (id int, color text, weight float)")
            for query in ok:
                cur.execute(query)
                assert True
            for query in bad:
                with pytest.raises(psycopg.errors.RaiseException):
                    cur.execute(query)
            con.rollback()


VECTORIZER_ROW = """
{
    "id": 1,
    "config": {
        "chunking": {
            "separator": " ",
            "chunk_size": 128,
            "chunk_column": "body",
            "chunk_overlap": 10,
            "implementation": "token_text_splitter"
        },
        "embedding": {
            "model": "text-embedding-3-small",
            "provider": "openai",
            "dimensions": 768
        },
        "formatting": {
            "columns": [
                "title",
                "published"
            ],
            "template": "title: $title published: $published $chunk",
            "implementation": "python_string_template"
        },
        "scheduling": {
            "job_id": 1000,
            "timezone": "America/Chicago",
            "initial_start": "2050-01-06T00:00:00+00:00",
            "implementation": "timescaledb",
            "schedule_interval": "00:05:00"
        }
    },
    "external": true,
    "source_pk": [
        {
            "pknum": 1,
            "attnum": 2,
            "attname": "title",
            "typname": "text",
            "attnotnull": true
        },
        {
            "pknum": 2,
            "attnum": 3,
            "attname": "published",
            "typname": "timestamptz",
            "attnotnull": true
        }
    ],
    "queue_table": "vectorizer_q_1",
    "asynchronous": true,
    "queue_schema": "ai",
    "source_table": "blog",
    "target_table": "blog_embedding",
    "source_schema": "website",
    "target_column": "embedding",
    "target_schema": "website"
}
"""


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
    vectorizer_src_trg_1 AFTER INSERT OR UPDATE ON website.blog FOR EACH ROW EXECUTE FUNCTION website.vectorizer_src_trg_1()
Access method: heap
""".strip()


SOURCE_TRIGGER_FUNC = """
                                                                                     List of functions
 Schema  |         Name         | Result data type | Argument data types | Type | Volatility | Parallel |  Owner   | Security | Access privileges | Language | Internal name | Description 
---------+----------------------+------------------+---------------------+------+------------+----------+----------+----------+-------------------+----------+---------------+-------------
 website | vectorizer_src_trg_1 | trigger          |                     | func | volatile   | unsafe   | postgres | invoker  |                   | plpgsql  |               | 
(1 row)
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
Access method: heap
""".strip()


def psql_cmd(cmd: str) -> str:
    cmd = f'''psql -X -d "{db_url('test')}" -c "{cmd}"'''
    proc = subprocess.run(cmd, shell=True, check=True, text=True, capture_output=True)
    return str(proc.stdout).strip()


def test_vectorizer():
    with psycopg.connect(db_url("postgres"), autocommit=True, row_factory=namedtuple_row) as con:
        with con.cursor() as cur:
            # set up the test
            cur.execute("create extension if not exists timescaledb")
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

            # create a vectorizer for the blog table
            # language=PostgreSQL
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
            , _scheduling=>ai.scheduling_config_timescaledb
                    ( interval '5m'
                    , _initial_start=>'2050-01-06'::timestamptz
                    , _timezone=>'America/Chicago'
                    )
            );
            """)
            vectorizer_id = cur.fetchone()[0]

            # check the vectorizer that was created
            cur.execute("""
                select jsonb_pretty(to_jsonb(x) #- array['config', 'version']) 
                from ai.vectorizer x 
                where x.id = %s
            """, (vectorizer_id,))
            actual = json.dumps(json.loads(cur.fetchone()[0]), sort_keys=True)
            expected = json.dumps(json.loads(VECTORIZER_ROW), sort_keys=True)
            assert actual == expected

            # check that the queue has 3 rows
            cur.execute("""
                select count(*)
                from ai.vectorizer_q_1
            """)
            actual = cur.fetchone()[0]
            assert actual == 3

            # get timescaledb job's job_id
            cur.execute("""
                select (x.config->'scheduling'->>'job_id')::int 
                from ai.vectorizer x 
                where x.id = %s
                """, (vectorizer_id,))
            job_id = cur.fetchone()[0]

            # check the timescaledb job that was created
            cur.execute("""
                select j.schedule_interval = interval '5m'
                and j.proc_schema = 'ai'
                and j.proc_name = '_vectorizer_async_ext_job'
                and j.scheduled = true
                and j.fixed_schedule = true
                as is_ok
                from timescaledb_information.jobs j
                where j.job_id = %s
            """, (job_id,))
            actual = cur.fetchone()[0]
            assert actual is True

            # run the timescaledb background job explicitly
            cur.execute("call public.run_job(%s)", (job_id,))

            # check that the queue has 0 rows
            cur.execute("""
                select count(*)
                from ai.vectorizer_q_1
            """)
            actual = cur.fetchone()[0]
            assert actual == 0

            # insert a row into the source
            cur.execute("""
                insert into website.blog(title, published, body)
                values
                  ('how to make ramen', '2021-01-06'::timestamptz, 'boil water. cook ramen in the water')
            """)
            # update a row into the source
            cur.execute("""
                update website.blog set published = now()
                where title = 'how to cook a hot dog'
            """)

            # check that the queue has 2 rows
            cur.execute("""
                select count(*)
                from ai.vectorizer_q_1
            """)
            actual = cur.fetchone()[0]
            assert actual == 2

            # run the underlying function explicitly
            # language=PostgreSQL
            cur.execute("call ai._vectorizer_async_ext_job(null, jsonb_build_object('vectorizer_id', %s))"
                        , (vectorizer_id,))

            # check that the queue has 0 rows
            cur.execute("""
                select count(*)
                from ai.vectorizer_q_1
            """)
            actual = cur.fetchone()[0]
            assert actual == 0

            # update a row into the source
            cur.execute("""
                update website.blog set published = now()
                where title = 'how to make ramen'
            """)

            # check that the queue has 1 rows
            cur.execute("""
                select count(*)
                from ai.vectorizer_q_1
            """)
            actual = cur.fetchone()[0]
            assert actual == 1

            # ping the external job explicitly
            # language=PostgreSQL
            cur.execute("select ai.execute_async_ext_vectorizer(%s)"
                        , (vectorizer_id,))

            # check that the queue has 0 rows
            cur.execute("""
                select count(*)
                from ai.vectorizer_q_1
            """)
            actual = cur.fetchone()[0]
            assert actual == 0

    # does the source table look right?
    actual = psql_cmd("\d+ website.blog")
    assert actual == SOURCE_TABLE

    # does the source trigger function look right?
    actual = psql_cmd("\df+ website.vectorizer_src_trg_1()")
    assert actual == SOURCE_TRIGGER_FUNC

    # does the target table look right?
    actual = psql_cmd("\d+ website.blog_embedding")
    assert actual == TARGET_TABLE

    # does the queue table look right?
    actual = psql_cmd("\d+ ai.vectorizer_q_1")
    assert actual == QUEUE_TABLE

