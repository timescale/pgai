import os
import subprocess
import json

import psycopg
from psycopg.rows import namedtuple_row
import pytest

# skip tests in this module if disabled
enable_vectorizer_tests = os.getenv("ENABLE_VECTORIZER_TESTS")
if not enable_vectorizer_tests or enable_vectorizer_tests == "0":
    pytest.skip(allow_module_level=True)


def db_url(user: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/test"


VECTORIZER_ROW = r"""
{
    "id": 1,
    "config": {
        "chunking": {
            "separator": "\n\n",
            "chunk_size": 128,
            "config_type": "chunking",
            "chunk_column": "body",
            "chunk_overlap": 10,
            "implementation": "character_text_splitter",
            "is_separator_regex": false
        },
        "indexing": {
            "min_rows": 100000,
            "config_type": "indexing",
            "implementation": "diskann"
        },
        "embedding": {
            "model": "text-embedding-3-small",
            "dimensions": 768,
            "config_type": "embedding",
            "api_key_name": "OPENAI_API_KEY",
            "implementation": "openai"
        },
        "formatting": {
            "columns": [
                "title",
                "published"
            ],
            "template": "title: $title published: $published $chunk",
            "config_type": "formatting",
            "implementation": "python_template"
        },
        "scheduling": {
            "job_id": 1000,
            "timezone": "America/Chicago",
            "config_type": "scheduling",
            "initial_start": "2050-01-06T00:00:00+00:00",
            "implementation": "timescaledb",
            "schedule_interval": "00:05:00"
        }
    },
    "source_pk": [
        {
            "pknum": 1,
            "attnum": 2,
            "attname": "title",
            "typname": "text"
        },
        {
            "pknum": 2,
            "attnum": 3,
            "attname": "published",
            "typname": "timestamptz"
        }
    ],
    "view_name": "blog_embedding",
    "queue_table": "_vectorizer_q_1",
    "view_schema": "website",
    "queue_schema": "ai",
    "source_table": "blog",
    "target_table": "blog_embedding_store",
    "trigger_name": "_vectorizer_src_trg_1",
    "source_schema": "website",
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
    TABLE "website.blog_embedding_store" CONSTRAINT "blog_embedding_store_title_published_fkey" FOREIGN KEY (title, published) REFERENCES website.blog(title, published) ON DELETE CASCADE
Triggers:
    _vectorizer_src_trg_1 AFTER INSERT OR UPDATE ON website.blog FOR EACH ROW EXECUTE FUNCTION ai._vectorizer_src_trg_1()
Access method: heap
""".strip()


SOURCE_TRIGGER_FUNC = """
                                                                                      List of functions
 Schema |         Name          | Result data type | Argument data types | Type | Volatility | Parallel |  Owner   | Security |  Access privileges  | Language | Internal name | Description 
--------+-----------------------+------------------+---------------------+------+------------+----------+----------+----------+---------------------+----------+---------------+-------------
 ai     | _vectorizer_src_trg_1 | trigger          |                     | func | volatile   | safe     | postgres | definer  | postgres=X/postgres | plpgsql  |               | 
(1 row)
""".strip()


TARGET_TABLE = """
                                                    Table "website.blog_embedding_store"
     Column     |           Type           | Collation | Nullable |      Default      | Storage  | Compression | Stats target | Description 
----------------+--------------------------+-----------+----------+-------------------+----------+-------------+--------------+-------------
 embedding_uuid | uuid                     |           | not null | gen_random_uuid() | plain    |             |              | 
 title          | text                     |           | not null |                   | extended |             |              | 
 published      | timestamp with time zone |           | not null |                   | plain    |             |              | 
 chunk_seq      | integer                  |           | not null |                   | plain    |             |              | 
 chunk          | text                     |           | not null |                   | extended |             |              | 
 embedding      | vector(768)              |           | not null |                   | external |             |              | 
Indexes:
    "blog_embedding_store_pkey" PRIMARY KEY, btree (embedding_uuid)
    "blog_embedding_store_title_published_chunk_seq_key" UNIQUE CONSTRAINT, btree (title, published, chunk_seq)
Foreign-key constraints:
    "blog_embedding_store_title_published_fkey" FOREIGN KEY (title, published) REFERENCES website.blog(title, published) ON DELETE CASCADE
Access method: heap
""".strip()


QUEUE_TABLE = """
                                                 Table "ai._vectorizer_q_1"
  Column   |           Type           | Collation | Nullable | Default | Storage  | Compression | Stats target | Description 
-----------+--------------------------+-----------+----------+---------+----------+-------------+--------------+-------------
 title     | text                     |           | not null |         | extended |             |              | 
 published | timestamp with time zone |           | not null |         | plain    |             |              | 
 queued_at | timestamp with time zone |           | not null | now()   | plain    |             |              | 
Indexes:
    "_vectorizer_q_1_title_published_idx" btree (title, published)
Access method: heap
""".strip()


VIEW = """
                                    View "website.blog_embedding"
     Column     |           Type           | Collation | Nullable | Default | Storage  | Description 
----------------+--------------------------+-----------+----------+---------+----------+-------------
 embedding_uuid | uuid                     |           |          |         | plain    | 
 chunk_seq      | integer                  |           |          |         | plain    | 
 chunk          | text                     |           |          |         | extended | 
 embedding      | vector(768)              |           |          |         | external | 
 id             | integer                  |           |          |         | plain    | 
 title          | text                     |           |          |         | extended | 
 published      | timestamp with time zone |           |          |         | plain    | 
 body           | text                     |           |          |         | extended | 
View definition:
 SELECT t.embedding_uuid,
    t.chunk_seq,
    t.chunk,
    t.embedding,
    s.id,
    t.title,
    t.published,
    s.body
   FROM website.blog_embedding_store t
     LEFT JOIN website.blog s ON t.title = s.title AND t.published = s.published;
""".strip()


def psql_cmd(cmd: str) -> str:
    cmd = f'''psql -X -d "{db_url('test')}" -c "{cmd}"'''
    proc = subprocess.run(cmd, shell=True, check=True, text=True, capture_output=True)
    return str(proc.stdout).strip()


def test_vectorizer_timescaledb():
    with psycopg.connect(db_url("postgres"), autocommit=True, row_factory=namedtuple_row) as con:
        with con.cursor() as cur:
            # set up the test
            cur.execute("create extension if not exists timescaledb")
            cur.execute("select to_regrole('bob') is null")
            if cur.fetchone()[0] is True:
                cur.execute("create user bob")
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
            cur.execute("""grant insert, update, delete on website.blog to bob""")
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
            , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
            , chunking=>ai.chunking_character_text_splitter('body', 128, 10)
            , formatting=>ai.formatting_python_template
                    ( 'title: $title published: $published $chunk'
                    , columns=>array['title', 'published']
                    )
            , scheduling=>ai.scheduling_timescaledb
                    ( interval '5m'
                    , initial_start=>'2050-01-06'::timestamptz
                    , timezone=>'America/Chicago'
                    )
            , grant_to=>array['bob', 'fernando']
            );
            """)
            vectorizer_id = cur.fetchone()[0]

            # check the vectorizer that was created
            cur.execute("""
                select jsonb_pretty(to_jsonb(x) #- array['config', 'version']) 
                from ai.vectorizer x 
                where x.id = %s
            """, (vectorizer_id,))
            actual = json.dumps(json.loads(cur.fetchone()[0]), sort_keys=True, indent=2)
            expected = json.dumps(json.loads(VECTORIZER_ROW), sort_keys=True, indent=2)
            assert actual == expected

            cur.execute("select * from ai.vectorizer where id = %s", (vectorizer_id,))
            vec = cur.fetchone()

            # check that the queue has 3 rows
            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer_id,))
            actual = cur.fetchone()[0]
            assert actual == 3

            # bob should have select on the source table
            cur.execute(f"select has_table_privilege('bob', 'website.blog', 'select')")
            actual = cur.fetchone()[0]
            assert actual

            # bob should have select, update, delete on the queue table
            cur.execute(f"select has_table_privilege('bob', '{vec.queue_schema}.{vec.queue_table}', 'select, update, delete')")
            actual = cur.fetchone()[0]
            assert actual

            # bob should have select, insert, update on the target table
            cur.execute(f"select has_table_privilege('bob', '{vec.target_schema}.{vec.target_table}', 'select, insert, update')")
            actual = cur.fetchone()[0]
            assert actual

            # bob should have select on the view
            cur.execute(f"select has_table_privilege('bob', '{vec.view_schema}.{vec.view_name}', 'select')")
            actual = cur.fetchone()[0]
            assert actual

            # bob should have select on the vectorizer table
            cur.execute("select has_table_privilege('bob', 'ai.vectorizer', 'select')")
            actual = cur.fetchone()[0]
            assert actual

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
                and j.proc_name = '_vectorizer_job'
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
            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer_id,))
            actual = cur.fetchone()[0]
            assert actual == 0

            # make sure bob can modify the source table and the trigger works
            with psycopg.connect(db_url("bob"), autocommit=False) as con2:
                with con2.cursor() as cur2:
                    # insert a row into the source
                    cur2.execute("""
                        insert into website.blog(title, published, body)
                        values
                          ('how to make ramen', '2021-01-06'::timestamptz, 'boil water. cook ramen in the water')
                    """)
                    # update a row into the source
                    cur2.execute("""
                        update website.blog set published = now()
                        where title = 'how to cook a hot dog'
                    """)

            # check that the queue has 2 rows
            cur.execute("select pending_items from ai.vectorizer_status where id = %s", (vectorizer_id,))
            actual = cur.fetchone()[0]
            assert actual == 2

            # run the underlying function explicitly
            # language=PostgreSQL
            cur.execute("call ai._vectorizer_job(null, jsonb_build_object('vectorizer_id', %s))"
                        , (vectorizer_id,))

            # check that the queue has 0 rows
            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer_id,))
            actual = cur.fetchone()[0]
            assert actual == 0

            # update a row into the source
            cur.execute("""
                update website.blog set published = now()
                where title = 'how to make ramen'
            """)

            # check that the queue has 1 rows
            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer_id,))
            actual = cur.fetchone()[0]
            assert actual == 1

            # check that using the GUCs work
            cur.execute("select set_config('ai.external_function_executor_url', 'http://localhost:8000', false)")
            cur.execute("select set_config('ai.external_functions_executor_events_path', '/api/v1/events', false)")

            # ping the external job explicitly
            # language=PostgreSQL
            cur.execute("select ai.execute_vectorizer(%s)"
                        , (vectorizer_id,))

            # check that the queue has 0 rows
            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer_id,))
            actual = cur.fetchone()[0]
            assert actual == 0

            # insert 2 rows into the source
            cur.execute("""
                insert into website.blog(title, published, body)
                values
                  ('how to grill a steak', '2020-01-06'::timestamptz, 'put it on a hot grill')
                , ('how to make pizza', '2019-01-06'::timestamptz, 'pick up the phone and order delivery')
            """)

            # lock 1 row in the queue and check the queue depth
            with psycopg.connect(db_url("postgres"), autocommit=False) as con2:
                with con2.cursor() as cur2:
                    cur2.execute("begin transaction")
                    # lock 1 row from the queue
                    cur2.execute(f"select * from {vec.queue_schema}.{vec.queue_table} where title = 'how to grill a steak' for update")
                    locked = cur2.fetchone()
                    # check that vectorizer queue depth still gets the correct count
                    cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer_id,))
                    actual = cur.fetchone()[0]
                    assert actual == 2
                    con2.rollback()

            # disable the schedule
            cur.execute("select ai.disable_vectorizer_schedule(%s)", (vectorizer_id,))

            # check that the timescaledb job is disabled
            cur.execute("""
                select scheduled
                from timescaledb_information.jobs j
                where j.job_id = %s
            """, (vec.config['scheduling']['job_id'],))
            actual = cur.fetchone()[0]
            assert actual is False

            # enable the schedule
            cur.execute("select ai.enable_vectorizer_schedule(%s)", (vectorizer_id,))

            # check that the timescaledb job is enabled
            cur.execute("""
                select scheduled
                from timescaledb_information.jobs j
                where j.job_id = %s
            """, (vec.config['scheduling']['job_id'],))
            actual = cur.fetchone()[0]
            assert actual is True

    # does the source table look right?
    actual = psql_cmd(r"\d+ website.blog")
    assert actual == SOURCE_TABLE

    # does the source trigger function look right?
    actual = psql_cmd(r"\df+ ai._vectorizer_src_trg_1()")
    assert actual == SOURCE_TRIGGER_FUNC

    # does the target table look right?
    actual = psql_cmd(r"\d+ website.blog_embedding_store")
    assert actual == TARGET_TABLE

    # does the queue table look right?
    actual = psql_cmd(r"\d+ ai._vectorizer_q_1")
    assert actual == QUEUE_TABLE

    # does the view look right?
    actual = psql_cmd(r"\d+ website.blog_embedding")
    assert actual == VIEW


def test_vectorizer_pg_cron():
    with psycopg.connect(db_url("postgres"), autocommit=True, row_factory=namedtuple_row) as con:
        with con.cursor() as cur:
            # set up the test
            cur.execute("select to_regrole('adelaide') is null")
            if cur.fetchone()[0] is True:
                cur.execute("create user adelaide")
            cur.execute("create extension if not exists pg_cron")
            cur.execute("drop table if exists public.chat")
            cur.execute("""
                create table public.chat
                ( id int not null primary key generated always as identity
                , parent_id int references public.chat (id) on delete cascade
                , author text not null
                , msg text not null
                , created_at timestamptz not null default now()
                )
            """)
            cur.execute("grant insert, update, delete on public.chat to adelaide")

            # create a vectorizer for the blog table
            # language=PostgreSQL
            cur.execute("""
            select ai.create_vectorizer
            ( 'public.chat'::regclass
            , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
            , chunking=>ai.chunking_character_text_splitter('msg', 128, 10)
            , formatting=>ai.formatting_python_template
                    ( 'author: $author created_at: $created_at $chunk'
                    , columns=>array['author', 'created_at']
                    )
            , scheduling=>ai.scheduling_pg_cron('*/10 * * * *')
            , grant_to=>null
            );
            """)
            vectorizer_id = cur.fetchone()[0]

            # check the scheduling config
            cur.execute("""
                select x.config->'scheduling' = jsonb_build_object
                ( 'implementation', 'pg_cron'
                , 'config_type', 'scheduling'
                , 'schedule', '*/10 * * * *'
                , 'job_id', 1
                )
                from ai.vectorizer x 
                where x.id = %s
            """, (vectorizer_id,))
            actual = cur.fetchone()[0]
            assert actual is True

            # check the pg_cron job table
            cur.execute("""
                select jobname, command
                from cron.job
                where jobid = 1
            """)
            actual = cur.fetchone()
            assert actual.jobname == f"vectorizer_{vectorizer_id}"
            assert actual.command == f"call ai._vectorizer_job(null, pg_catalog.jsonb_build_object('vectorizer_id', {vectorizer_id}))"

            # disable the schedule
            cur.execute("select ai.disable_vectorizer_schedule(%s)", (vectorizer_id,))

            # check that the pg_cron job is disabled
            cur.execute("""
                select active
                from cron.job
                where jobid = 1
            """)
            actual = cur.fetchone()[0]
            assert actual is False

            # enable the schedule
            cur.execute("select ai.enable_vectorizer_schedule(%s)", (vectorizer_id,))

            # check that the pg_cron job is enabled
            cur.execute("""
                select active
                from cron.job
                where jobid = 1
            """)
            actual = cur.fetchone()[0]
            assert actual is True

            # make sure adelaide can modify the source table and the trigger works
            with psycopg.connect(db_url("adelaide"), autocommit=False) as con2:
                with con2.cursor() as cur2:
                    # insert a row into the source
                    cur2.execute("""
                        insert into public.chat(author, msg)
                        values ('adelaide', 'hello world')
                    """)

            # check that the queue has 1 rows
            cur.execute("select pending_items from ai.vectorizer_status where id = %s", (vectorizer_id,))
            actual = cur.fetchone()[0]
            assert actual == 1


def test_drop_vectorizer():
    with psycopg.connect(db_url("postgres"), autocommit=True, row_factory=namedtuple_row) as con:
        with con.cursor() as cur:
            # set up the test
            cur.execute("create extension if not exists timescaledb")
            cur.execute("drop schema if exists wiki cascade")
            cur.execute("create schema wiki")
            cur.execute("drop table if exists wiki.post")
            cur.execute("""
                create table wiki.post
                ( id serial not null primary key
                , title text not null
                , published timestamptz
                , category text
                , tags text[]
                , content text not null
                )
            """)
            cur.execute("""
                insert into wiki.post(title, published, category, tags, content)
                values
                  ( 'how to cook a hot dog'
                  , '2024-01-06'::timestamptz
                  , 'recipies'
                  , array['grill', 'fast']
                  , 'put it on a hot grill'
                  )
            """)

            # create a vectorizer for the blog table
            # language=PostgreSQL
            cur.execute("""
            select ai.create_vectorizer
            ( 'wiki.post'::regclass
            , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
            , chunking=>ai.chunking_character_text_splitter('content', 128, 10)
            , scheduling=>ai.scheduling_timescaledb()
            , grant_to=>null
            );
            """)
            vectorizer_id = cur.fetchone()[0]

            cur.execute("select * from ai.vectorizer where id = %s", (vectorizer_id,))
            vectorizer = cur.fetchone()

            # does the target table exist? (it should)
            cur.execute(f"select to_regclass('{vectorizer.target_schema}.{vectorizer.target_table}') is not null")
            actual = cur.fetchone()[0]
            assert actual is True

            # does the queue table exist? (it should)
            cur.execute(f"select to_regclass('{vectorizer.queue_schema}.{vectorizer.queue_table}') is not null")
            actual = cur.fetchone()[0]
            assert actual is True

            # does the view exist? (it should)
            cur.execute(f"select to_regclass('{vectorizer.view_schema}.{vectorizer.view_name}') is not null")
            actual = cur.fetchone()[0]
            assert actual is True

            # do the trigger and backing function exist? (it should)
            cur.execute(f"""
                select g.tgfoid
                from pg_trigger g
                where g.tgname = '{vectorizer.trigger_name}'
                and g.tgrelid = '{vectorizer.source_schema}.{vectorizer.source_table}'::regclass::oid
                ;
            """)
            assert cur.rownumber is not None
            pg_proc_oid = cur.fetchone()[0]

            # drop the vectorizer
            cur.execute("select ai.drop_vectorizer(%s)", (vectorizer_id,))

            # does the target table exist? (it SHOULD)
            cur.execute(f"select to_regclass('{vectorizer.target_schema}.{vectorizer.target_table}') is not null")
            actual = cur.fetchone()[0]
            assert actual is True

            # does the queue table exist? (it should not)
            cur.execute(f"select to_regclass('{vectorizer.queue_schema}.{vectorizer.queue_table}') is not null")
            actual = cur.fetchone()[0]
            assert actual is False

            # does the view exist? (it SHOULD)
            cur.execute(f"select to_regclass('{vectorizer.view_schema}.{vectorizer.view_name}') is not null")
            actual = cur.fetchone()[0]
            assert actual is True

            # does the trigger exist? (it should not)
            cur.execute(f"""
                select count(*)
                from pg_trigger g
                where g.tgname = '{vectorizer.trigger_name}'
                and g.tgrelid = '{vectorizer.source_schema}.{vectorizer.source_table}'::regclass::oid
                ;
            """)
            actual = cur.fetchone()[0]
            assert actual == 0

            # does the func that backed the trigger exist? (it should not)
            cur.execute(f"""
                select count(*)
                from pg_proc
                where oid = %s
            """, (pg_proc_oid,))
            actual = cur.fetchone()[0]
            assert actual == 0

            # does the timescaledb job exist? (it should not)
            cur.execute(f"""
                select count(*)
                from timescaledb_information.jobs
                where job_id = %s
            """, (vectorizer.config['scheduling']['job_id'],))
            actual = cur.fetchone()[0]
            assert actual == 0
