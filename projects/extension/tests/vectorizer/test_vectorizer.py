import json
import os
import subprocess

import psycopg
import pytest
from psycopg.rows import namedtuple_row

# skip tests in this module if disabled
enable_vectorizer_tests = os.getenv("ENABLE_VECTORIZER_TESTS")
if enable_vectorizer_tests == "0":
    pytest.skip(allow_module_level=True)


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
            "config_type": "indexing",
            "implementation": "none"
        },
        "embedding": {
            "model": "text-embedding-3-small",
            "dimensions": 768,
            "config_type": "embedding",
            "api_key_name": "OPENAI_API_KEY",
            "implementation": "openai"
        },
        "formatting": {
            "template": "title: $title published: $published $chunk",
            "config_type": "formatting",
            "implementation": "python_template"
        },
        "processing": {
            "config_type": "processing",
            "implementation": "default"
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
 Schema |         Name          | Result data type | Argument data types | Type | Volatility | Parallel | Owner | Security | Access privileges | Language | Internal name | Description 
--------+-----------------------+------------------+---------------------+------+------------+----------+-------+----------+-------------------+----------+---------------+-------------
 ai     | _vectorizer_src_trg_1 | trigger          |                     | func | volatile   | safe     | test  | definer  | test=X/test       | plpgsql  |               | 
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


def db_url(user: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/test"


def psql_cmd(cmd: str) -> str:
    cmd = f'''psql -X -d "{db_url('test')}" -c "{cmd}"'''
    proc = subprocess.run(cmd, shell=True, check=True, text=True, capture_output=True)
    return str(proc.stdout).strip()


def test_vectorizer_timescaledb():
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
    with psycopg.connect(
        db_url("test"), autocommit=True, row_factory=namedtuple_row
    ) as con:
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

            # create a vectorizer for the blog table
            # language=PostgreSQL
            cur.execute("""
            select ai.create_vectorizer
            ( 'website.blog'::regclass
            , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
            , chunking=>ai.chunking_character_text_splitter('body', 128, 10)
            , formatting=>ai.formatting_python_template('title: $title published: $published $chunk')
            , scheduling=>ai.scheduling_timescaledb
                    ( interval '5m'
                    , initial_start=>'2050-01-06'::timestamptz
                    , timezone=>'America/Chicago'
                    )
            , grant_to=>ai.grant_to('bob', 'fernando') -- bob is good. fernando doesn't exist. don't grant to adelaide
            );
            """)
            vectorizer_id = cur.fetchone()[0]

            # check the vectorizer that was created
            cur.execute(
                """
                select jsonb_pretty(to_jsonb(x) #- array['config', 'version']) 
                from ai.vectorizer x 
                where x.id = %s
            """,
                (vectorizer_id,),
            )
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
            cur.execute("select has_table_privilege('bob', 'website.blog', 'select')")
            actual = cur.fetchone()[0]
            assert actual

            # bob should have select, update, delete on the queue table
            cur.execute(
                f"select has_table_privilege('bob', '{vec.queue_schema}.{vec.queue_table}', 'select, update, delete')"
            )
            actual = cur.fetchone()[0]
            assert actual

            # bob should have select, insert, update on the target table
            cur.execute(
                f"select has_table_privilege('bob', '{vec.target_schema}.{vec.target_table}', 'select, insert, update')"
            )
            actual = cur.fetchone()[0]
            assert actual

            # bob should have select on the view
            cur.execute(
                f"select has_table_privilege('bob', '{vec.view_schema}.{vec.view_name}', 'select')"
            )
            actual = cur.fetchone()[0]
            assert actual

            # bob should have select on the vectorizer table
            cur.execute("select has_table_privilege('bob', 'ai.vectorizer', 'select')")
            actual = cur.fetchone()[0]
            assert actual

            # get timescaledb job's job_id
            cur.execute(
                """
                select (x.config->'scheduling'->>'job_id')::int 
                from ai.vectorizer x 
                where x.id = %s
                """,
                (vectorizer_id,),
            )
            job_id = cur.fetchone()[0]

            # check the timescaledb job that was created
            cur.execute(
                """
                select j.schedule_interval = interval '5m'
                and j.proc_schema = 'ai'
                and j.proc_name = '_vectorizer_job'
                and j.scheduled = true
                and j.fixed_schedule = true
                as is_ok
                from timescaledb_information.jobs j
                where j.job_id = %s
            """,
                (job_id,),
            )
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
            # make sure adelaide can modify the source table and the trigger works
            with psycopg.connect(db_url("adelaide"), autocommit=False) as con2:
                with con2.cursor() as cur2:
                    # update a row into the source
                    cur2.execute("""
                        update website.blog set published = now()
                        where title = 'how to cook a hot dog'
                    """)

            # check that the queue has 2 rows
            cur.execute(
                "select pending_items from ai.vectorizer_status where id = %s",
                (vectorizer_id,),
            )
            actual = cur.fetchone()[0]
            assert actual == 2

            # run the underlying function explicitly
            # language=PostgreSQL
            cur.execute(
                "call ai._vectorizer_job(null, jsonb_build_object('vectorizer_id', %s))",
                (vectorizer_id,),
            )

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
            cur.execute(
                "select set_config('ai.external_functions_executor_url', 'http://localhost:8000', false)"
            )
            cur.execute(
                "select set_config('ai.external_functions_executor_events_path', '/api/v1/events', false)"
            )

            # ping the external job explicitly
            # language=PostgreSQL
            cur.execute("select ai.execute_vectorizer(%s)", (vectorizer_id,))

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
            with psycopg.connect(db_url("test"), autocommit=False) as con2:
                with con2.cursor() as cur2:
                    cur2.execute("begin transaction")
                    # lock 1 row from the queue
                    cur2.execute(
                        f"select * from {vec.queue_schema}.{vec.queue_table} where title = 'how to grill a steak' for update"
                    )
                    cur2.fetchone()
                    # check that vectorizer queue depth still gets the correct count
                    cur.execute(
                        "select ai.vectorizer_queue_pending(%s)", (vectorizer_id,)
                    )
                    actual = cur.fetchone()[0]
                    assert actual == 2
                    con2.rollback()

            # disable the schedule
            cur.execute("select ai.disable_vectorizer_schedule(%s)", (vectorizer_id,))

            # check that the timescaledb job is disabled
            cur.execute(
                """
                select scheduled
                from timescaledb_information.jobs j
                where j.job_id = %s
            """,
                (vec.config["scheduling"]["job_id"],),
            )
            actual = cur.fetchone()[0]
            assert actual is False

            # enable the schedule
            cur.execute("select ai.enable_vectorizer_schedule(%s)", (vectorizer_id,))

            # check that the timescaledb job is enabled
            cur.execute(
                """
                select scheduled
                from timescaledb_information.jobs j
                where j.job_id = %s
            """,
                (vec.config["scheduling"]["job_id"],),
            )
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


def test_drop_vectorizer():
    with psycopg.connect(
        db_url("test"), autocommit=True, row_factory=namedtuple_row
    ) as con:
        with con.cursor() as cur:
            cur.execute("create extension if not exists ai cascade")
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
            cur.execute(
                f"select to_regclass('{vectorizer.target_schema}.{vectorizer.target_table}') is not null"
            )
            actual = cur.fetchone()[0]
            assert actual is True

            # does the queue table exist? (it should)
            cur.execute(
                f"select to_regclass('{vectorizer.queue_schema}.{vectorizer.queue_table}') is not null"
            )
            actual = cur.fetchone()[0]
            assert actual is True

            # does the view exist? (it should)
            cur.execute(
                f"select to_regclass('{vectorizer.view_schema}.{vectorizer.view_name}') is not null"
            )
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
            cur.execute(
                f"select to_regclass('{vectorizer.target_schema}.{vectorizer.target_table}') is not null"
            )
            actual = cur.fetchone()[0]
            assert actual is True

            # does the queue table exist? (it should not)
            cur.execute(
                f"select to_regclass('{vectorizer.queue_schema}.{vectorizer.queue_table}') is not null"
            )
            actual = cur.fetchone()[0]
            assert actual is False

            # does the view exist? (it SHOULD)
            cur.execute(
                f"select to_regclass('{vectorizer.view_schema}.{vectorizer.view_name}') is not null"
            )
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
            cur.execute(
                """
                select count(*)
                from pg_proc
                where oid = %s
            """,
                (pg_proc_oid,),
            )
            actual = cur.fetchone()[0]
            assert actual == 0

            # does the timescaledb job exist? (it should not)
            cur.execute(
                """
                select count(*)
                from timescaledb_information.jobs
                where job_id = %s
            """,
                (vectorizer.config["scheduling"]["job_id"],),
            )
            actual = cur.fetchone()[0]
            assert actual == 0


def test_drop_source():
    with psycopg.connect(
        db_url("test"), autocommit=True, row_factory=namedtuple_row
    ) as con:
        with con.cursor() as cur:
            cur.execute("create extension if not exists ai cascade")
            cur.execute("create extension if not exists timescaledb")
            cur.execute("drop table if exists public.blog_drop")
            cur.execute("""
                create table public.blog_drop
                ( id serial not null primary key
                , title text not null
                , published timestamptz
                , category text
                , tags text[]
                , content text not null
                )
            """)

            # create a vectorizer for the table
            # language=PostgreSQL
            cur.execute("""
            select ai.create_vectorizer
            ( 'public.blog_drop'::regclass
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
            cur.execute(
                f"select to_regclass('{vectorizer.target_schema}.{vectorizer.target_table}') is not null"
            )
            actual = cur.fetchone()[0]
            assert actual is True

            # does the queue table exist? (it should)
            cur.execute(
                f"select to_regclass('{vectorizer.queue_schema}.{vectorizer.queue_table}') is not null"
            )
            actual = cur.fetchone()[0]
            assert actual is True

            # does the view exist? (it should)
            cur.execute(
                f"select to_regclass('{vectorizer.view_schema}.{vectorizer.view_name}') is not null"
            )
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

            # have to drop the foreign key in order to drop the source
            cur.execute(f"""
                alter table {vectorizer.target_schema}.{vectorizer.target_table} 
                drop constraint blog_drop_embedding_store_id_fkey restrict
                """)

            # drop the source table
            # this should fire the event trigger and drop the vectorizer
            cur.execute(
                f"drop table {vectorizer.source_schema}.{vectorizer.source_table} cascade"
            )

            # does the vectorizer row exist? (it should NOT)
            cur.execute(
                "select count(*) filter (where id = %s) from ai.vectorizer",
                (vectorizer_id,),
            )
            actual = cur.fetchone()[0]
            assert actual == 0

            # does the target table exist? (it SHOULD)
            cur.execute(
                f"select to_regclass('{vectorizer.target_schema}.{vectorizer.target_table}') is not null"
            )
            actual = cur.fetchone()[0]
            assert actual is True

            # does the queue table exist? (it should not b/c of cascade)
            cur.execute(
                f"select to_regclass('{vectorizer.queue_schema}.{vectorizer.queue_table}') is not null"
            )
            actual = cur.fetchone()[0]
            assert actual is False

            # does the view exist? (it should not)
            cur.execute(
                f"select to_regclass('{vectorizer.view_schema}.{vectorizer.view_name}') is not null"
            )
            actual = cur.fetchone()[0]
            assert actual is False

            # does the trigger exist? (it should not)
            cur.execute(f"""
                select count(*)
                from pg_trigger g
                where g.tgname = '{vectorizer.trigger_name}'
                ;
            """)
            actual = cur.fetchone()[0]
            assert actual == 0

            # does the func that backed the trigger exist? (it should not)
            cur.execute(
                """
                select count(*)
                from pg_proc
                where oid = %s
            """,
                (pg_proc_oid,),
            )
            actual = cur.fetchone()[0]
            assert actual == 0

            # does the timescaledb job exist? (it should not)
            cur.execute(
                """
                select count(*)
                from timescaledb_information.jobs
                where job_id = %s
            """,
                (vectorizer.config["scheduling"]["job_id"],),
            )
            actual = cur.fetchone()[0]
            assert actual == 0


def index_creation_tester(cur: psycopg.Cursor, vectorizer_id: int) -> None:
    cur.execute("select * from ai.vectorizer where id = %s", (vectorizer_id,))
    vectorizer = cur.fetchone()

    # make sure the index does NOT exist
    cur.execute(
        """
                select ai._vectorizer_vector_index_exists(v.target_schema, v.target_table, v.config->'indexing')
                from ai.vectorizer v
                where v.id = %s
            """,
        (vectorizer_id,),
    )
    actual = cur.fetchone()[0]
    assert actual is False

    # run the job
    cur.execute(
        "call ai._vectorizer_job(null, jsonb_build_object('vectorizer_id', %s))",
        (vectorizer_id,),
    )

    # make sure the index does NOT exist
    cur.execute(
        """
                select ai._vectorizer_vector_index_exists(v.target_schema, v.target_table, v.config->'indexing')
                from ai.vectorizer v
                where v.id = %s
            """,
        (vectorizer_id,),
    )
    actual = cur.fetchone()[0]
    assert actual is False

    # insert 5 rows into the target
    cur.execute(f"""
                insert into {vectorizer.target_schema}.{vectorizer.target_table}
                ( embedding_uuid
                , id
                , chunk_seq
                , chunk 
                , embedding
                )
                select
                  gen_random_uuid()
                , x
                , 0
                , 'i am a chunk'
                , (select array_agg(random()) from generate_series(1, 3))::vector(3)
                from generate_series(1,5) x
            """)

    # run the job
    cur.execute(
        "call ai._vectorizer_job(null, jsonb_build_object('vectorizer_id', %s))",
        (vectorizer_id,),
    )

    # make sure the index does NOT exist (min_rows = 10)
    cur.execute(
        """
                select ai._vectorizer_vector_index_exists(v.target_schema, v.target_table, v.config->'indexing')
                from ai.vectorizer v
                where v.id = %s
            """,
        (vectorizer_id,),
    )
    actual = cur.fetchone()[0]
    assert actual is False

    # insert 5 rows into the target
    cur.execute(f"""
                insert into {vectorizer.target_schema}.{vectorizer.target_table}
                ( embedding_uuid
                , id
                , chunk_seq
                , chunk 
                , embedding
                )
                select
                  gen_random_uuid()
                , x
                , 1
                , 'i am a chunk'
                , (select array_agg(random()) from generate_series(1, 3))::vector(3)
                from generate_series(1,5) x
            """)

    # insert some rows into the queue. this should prevent the index from being created
    cur.execute(
        f"insert into {vectorizer.queue_schema}.{vectorizer.queue_table}(id) select generate_series(1, 5)"
    )

    # should NOT create index
    cur.execute(
        """
        select ai._vectorizer_should_create_vector_index(v)
        from ai.vectorizer v
        where v.id = %s
    """,
        (vectorizer_id,),
    )
    actual = cur.fetchone()[0]
    assert actual is False

    # run the job
    cur.execute(
        "call ai._vectorizer_job(null, jsonb_build_object('vectorizer_id', %s))",
        (vectorizer_id,),
    )

    # make sure the index does NOT exist (queue table is NOT empty)
    cur.execute(
        """
                select ai._vectorizer_vector_index_exists(v.target_schema, v.target_table, v.config->'indexing')
                from ai.vectorizer v
                where v.id = %s
            """,
        (vectorizer_id,),
    )
    actual = cur.fetchone()[0]
    assert actual is False

    # empty the queue
    cur.execute(f"delete from {vectorizer.queue_schema}.{vectorizer.queue_table}")

    # SHOULD create index
    cur.execute(
        """
        select ai._vectorizer_should_create_vector_index(v)
        from ai.vectorizer v
        where v.id = %s
    """,
        (vectorizer_id,),
    )
    actual = cur.fetchone()[0]
    assert actual is True

    # run the job
    cur.execute(
        "call ai._vectorizer_job(null, jsonb_build_object('vectorizer_id', %s))",
        (vectorizer_id,),
    )

    # make sure the index ****DOES**** exist  (min_rows = 10 and 10 rows exist AND queue table is empty)
    cur.execute(
        """
                select ai._vectorizer_vector_index_exists(v.target_schema, v.target_table, v.config->'indexing')
                from ai.vectorizer v
                where v.id = %s
            """,
        (vectorizer_id,),
    )
    actual = cur.fetchone()[0]
    assert actual is True


def test_diskann_index():
    # pgvectorscale must be installed by a superuser
    with psycopg.connect(
        db_url("postgres"), autocommit=True, row_factory=namedtuple_row
    ) as con:
        with con.cursor() as cur:
            cur.execute("create extension if not exists vectorscale cascade")
    with psycopg.connect(
        db_url("test"), autocommit=True, row_factory=namedtuple_row
    ) as con:
        with con.cursor() as cur:
            cur.execute("create extension if not exists ai cascade")
            cur.execute("create extension if not exists timescaledb")
            cur.execute("create schema if not exists vec")
            cur.execute("drop table if exists vec.note0")
            cur.execute("""
                create table vec.note0
                ( id bigint not null primary key generated always as identity
                , note text not null
                )
            """)
            # insert 5 rows into source
            cur.execute("""
                insert into vec.note0 (note)
                select 'i am a note'
                from generate_series(1, 5)
            """)

            # create a vectorizer for the table
            # language=PostgreSQL
            cur.execute("""
            select ai.create_vectorizer
            ( 'vec.note0'::regclass
            , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
            , chunking=>ai.chunking_character_text_splitter('note')
            , scheduling=>
                ai.scheduling_timescaledb
                ( interval '5m'
                , initial_start=>'2050-01-06'::timestamptz
                , timezone=>'America/Chicago'
                )
            , indexing=>ai.indexing_diskann(min_rows=>10)
            , grant_to=>null
            , enqueue_existing=>false
            );
            """)
            vectorizer_id = cur.fetchone()[0]

            index_creation_tester(cur, vectorizer_id)


def test_hnsw_index():
    with psycopg.connect(
        db_url("test"), autocommit=True, row_factory=namedtuple_row
    ) as con:
        with con.cursor() as cur:
            cur.execute("create extension if not exists ai cascade")
            cur.execute("create extension if not exists timescaledb")
            cur.execute("create schema if not exists vec")
            cur.execute("drop table if exists vec.note1")
            cur.execute("""
                create table vec.note1
                ( id bigint not null primary key generated always as identity
                , note text not null
                )
            """)
            # insert 5 rows into source
            cur.execute("""
                insert into vec.note1 (note)
                select 'i am a note'
                from generate_series(1, 5)
            """)

            # create a vectorizer for the table
            # language=PostgreSQL
            cur.execute("""
            select ai.create_vectorizer
            ( 'vec.note1'::regclass
            , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
            , chunking=>ai.chunking_character_text_splitter('note')
            , scheduling=>
                ai.scheduling_timescaledb
                ( interval '5m'
                , initial_start=>'2050-01-06'::timestamptz
                , timezone=>'America/Chicago'
                )
            , indexing=>ai.indexing_hnsw(min_rows=>10, m=>20)
            , grant_to=>null
            , enqueue_existing=>false
            );
            """)
            vectorizer_id = cur.fetchone()[0]

            index_creation_tester(cur, vectorizer_id)


def test_index_create_concurrency():
    # pgvectorscale must be installed by a superuser
    with psycopg.connect(
        db_url("postgres"), autocommit=True, row_factory=namedtuple_row
    ) as con:
        with con.cursor() as cur:
            cur.execute("create extension if not exists vectorscale cascade")
    with psycopg.connect(
        db_url("test"), autocommit=True, row_factory=namedtuple_row
    ) as con:
        with con.cursor() as cur:
            cur.execute("create extension if not exists ai cascade")
            cur.execute("create extension if not exists timescaledb")
            cur.execute("create schema if not exists vec")
            cur.execute("drop table if exists vec.note2")
            cur.execute("""
                create table vec.note2
                ( id bigint not null primary key generated always as identity
                , note text not null
                )
            """)
            # insert 10 rows into source
            cur.execute("""
                insert into vec.note2 (note)
                select 'i am a note'
                from generate_series(1, 10)
            """)

            # create a vectorizer for the table
            # language=PostgreSQL
            cur.execute("""
            select ai.create_vectorizer
            ( 'vec.note2'::regclass
            , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
            , chunking=>ai.chunking_character_text_splitter('note')
            , scheduling=>
                ai.scheduling_timescaledb
                ( interval '5m'
                , initial_start=>'2050-01-06'::timestamptz
                , timezone=>'America/Chicago'
                )
            , indexing=>
                ai.indexing_diskann
                ( min_rows=>10
                , num_neighbors=>25
                , search_list_size=>50
                , create_when_queue_empty=>false
                )
            , grant_to=>null
            , enqueue_existing=>false
            );
            """)
            vectorizer_id = cur.fetchone()[0]

            cur.execute("select * from ai.vectorizer where id = %s", (vectorizer_id,))
            vectorizer = cur.fetchone()

            # make sure the index does NOT exist (min_rows = 10)
            cur.execute(
                """
                        select ai._vectorizer_vector_index_exists(v.target_schema, v.target_table, v.config->'indexing')
                        from ai.vectorizer v
                        where v.id = %s
                    """,
                (vectorizer_id,),
            )
            actual = cur.fetchone()[0]
            assert actual is False

            # insert 10 rows into the target
            cur.execute(f"""
                        insert into {vectorizer.target_schema}.{vectorizer.target_table}
                        ( embedding_uuid
                        , id
                        , chunk_seq
                        , chunk 
                        , embedding
                        )
                        select
                          gen_random_uuid()
                        , x
                        , 0
                        , 'i am a chunk'
                        , (select array_agg(random()) from generate_series(1, 3))::vector(3)
                        from generate_series(1,10) x
                    """)

            # explicitly create the index but hold the transaction open and run the job in another transaction
            with psycopg.connect(db_url("test"), autocommit=False) as con2:
                with con2.cursor() as cur2:
                    cur2.execute(
                        """
                        select ai._vectorizer_create_vector_index(v.target_schema, v.target_table, v.config->'indexing')
                        from ai.vectorizer v
                        where v.id = %s
                        """,
                        (vectorizer_id,),
                    )
                    # hold the transaction open
                    # try to explicitly create the index on the other connection
                    cur.execute(
                        """
                        select ai._vectorizer_create_vector_index(v.target_schema, v.target_table, v.config->'indexing')
                        from ai.vectorizer v
                        where v.id = %s
                        """,
                        (vectorizer_id,),
                    )
                    con2.commit()

            # make sure the index DOES exist (min_rows = 10)
            cur.execute(
                """
                        select ai._vectorizer_vector_index_exists(v.target_schema, v.target_table, v.config->'indexing')
                        from ai.vectorizer v
                        where v.id = %s
                    """,
                (vectorizer_id,),
            )
            actual = cur.fetchone()[0]
            assert actual is True

            # make sure there is only ONE index
            cur.execute(
                """
                select pg_catalog.count(*) filter
                ( where pg_catalog.pg_get_indexdef(i.indexrelid)
                  ilike '%% using diskann %%'
                )
                from pg_catalog.pg_class k
                inner join pg_catalog.pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
                inner join pg_index i on (k.oid operator(pg_catalog.=) i.indrelid)
                inner join pg_catalog.pg_attribute a
                    on (k.oid operator(pg_catalog.=) a.attrelid
                    and a.attname operator(pg_catalog.=) 'embedding'
                    and a.attnum operator(pg_catalog.=) i.indkey[0]
                    )
                inner join ai.vectorizer v 
                on (n.nspname operator(pg_catalog.=) v.target_schema
                and k.relname operator(pg_catalog.=) v.target_table)
                where v.id = %s
            """,
                (vectorizer_id,),
            )
            actual = cur.fetchone()[0]
            assert actual == 1


def test_naming_collisions():
    with psycopg.connect(
        db_url("test"), autocommit=True, row_factory=namedtuple_row
    ) as con:
        with con.cursor() as cur:
            cur.execute("create extension if not exists ai cascade")
            cur.execute("create extension if not exists timescaledb")
            cur.execute("create schema if not exists vec")
            cur.execute("drop table if exists vec.note4")
            cur.execute("""
                create table vec.note4
                ( id bigint not null primary key generated always as identity
                , note text not null
                )
            """)

            # create a vectorizer for the table
            # language=PostgreSQL
            cur.execute("""
            select ai.create_vectorizer
            ( 'vec.note4'::regclass
            , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
            , chunking=>ai.chunking_character_text_splitter('note')
            , scheduling=>ai.scheduling_none()
            , indexing=>ai.indexing_none()
            , grant_to=>null
            , enqueue_existing=>false
            );
            """)

            # try to create another one, fail on view_name / destination collision
            # language=PostgreSQL
            with pytest.raises(
                psycopg.errors.RaiseException,
                match=".*specify an alternate destination explicitly*",
            ):
                cur.execute("""
                select ai.create_vectorizer
                ( 'vec.note4'::regclass
                , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
                , chunking=>ai.chunking_character_text_splitter('note')
                , scheduling=>ai.scheduling_none()
                , indexing=>ai.indexing_none()
                , grant_to=>null
                , enqueue_existing=>false
                );
                """)

            # try to create another one, fail on target_table name collision
            # language=PostgreSQL
            with pytest.raises(
                psycopg.errors.RaiseException,
                match=".*specify an alternate destination or target_table explicitly*",
            ):
                cur.execute("""
                select ai.create_vectorizer
                ( 'vec.note4'::regclass
                , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
                , chunking=>ai.chunking_character_text_splitter('note')
                , scheduling=>ai.scheduling_none()
                , indexing=>ai.indexing_none()
                , grant_to=>null
                , enqueue_existing=>false
                , view_schema=>'ai'
                , view_name=>'note4_embedding2'
                );
                """)

            # try to create another one, fail on queue_table name collision
            # language=PostgreSQL
            with pytest.raises(
                psycopg.errors.RaiseException,
                match=".*specify an alternate queue_table explicitly*",
            ):
                cur.execute("""
                select ai.create_vectorizer
                ( 'vec.note4'::regclass
                , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
                , chunking=>ai.chunking_character_text_splitter('note')
                , scheduling=>ai.scheduling_none()
                , indexing=>ai.indexing_none()
                , grant_to=>null
                , enqueue_existing=>false
                , view_schema=>'ai'
                , view_name=>'note4_embedding2'
                , target_schema=>'vec'
                , target_table=>'note4_embedding_store2'
                , queue_schema=>'ai'
                , queue_table=>'_vectorizer_q_1'
                );
                """)

            # try to create another one, this should work
            # language=PostgreSQL
            cur.execute("""
            select ai.create_vectorizer
            ( 'vec.note4'::regclass
            , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
            , chunking=>ai.chunking_character_text_splitter('note')
            , scheduling=>ai.scheduling_none()
            , indexing=>ai.indexing_none()
            , grant_to=>null
            , enqueue_existing=>false
            , target_schema=>'vec'
            , target_table=>'note4_embedding_store2'
            , queue_schema=>'ai'
            , queue_table=>'this_is_a_queue_table'
            , view_schema=>'vec'
            , view_name=>'note4_embedding2'
            );
            """)
            vectorizer_id = cur.fetchone()[0]
            cur.execute("select * from ai.vectorizer where id = %s", (vectorizer_id,))
            vectorizer = cur.fetchone()
            assert vectorizer.target_schema == "vec"
            assert vectorizer.target_table == "note4_embedding_store2"
            assert vectorizer.queue_schema == "ai"
            assert vectorizer.queue_table == "this_is_a_queue_table"
            assert vectorizer.view_schema == "vec"
            assert vectorizer.view_name == "note4_embedding2"
            cur.execute("""
                select to_regclass('vec.note4_embedding_store2') is not null
                and to_regclass('ai.this_is_a_queue_table') is not null
                and to_regclass('vec.note4_embedding2') is not null
            """)
            assert cur.fetchone()[0]

            # try to create another one, this should work too (by using destination)!
            # language=PostgreSQL
            cur.execute("""
            select ai.create_vectorizer
            ( 'vec.note4'::regclass
            , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
            , chunking=>ai.chunking_character_text_splitter('note')
            , scheduling=>ai.scheduling_none()
            , indexing=>ai.indexing_none()
            , grant_to=>null
            , enqueue_existing=>false
            , destination=>'fernando'
            );
            """)
            vectorizer_id = cur.fetchone()[0]
            cur.execute("select * from ai.vectorizer where id = %s", (vectorizer_id,))
            vectorizer = cur.fetchone()
            assert vectorizer.target_schema == "vec"
            assert vectorizer.target_table == "fernando_store"
            assert vectorizer.queue_schema == "ai"
            assert vectorizer.queue_table == f"_vectorizer_q_{vectorizer.id}"
            assert vectorizer.view_schema == "vec"
            assert vectorizer.view_name == "fernando"
            cur.execute(f"""
                select to_regclass('vec.fernando_store') is not null
                and to_regclass('ai._vectorizer_q_{vectorizer.id}') is not null
                and to_regclass('vec.fernando') is not null
            """)
            assert cur.fetchone()[0]


def test_none_index_scheduling():
    with psycopg.connect(
        db_url("test"), autocommit=True, row_factory=namedtuple_row
    ) as con:
        with con.cursor() as cur:
            cur.execute("create extension if not exists ai cascade")
            cur.execute("create extension if not exists timescaledb")
            cur.execute("create schema if not exists vec")
            cur.execute("drop table if exists vec.note3")
            cur.execute("""
                create table vec.note3
                ( id bigint not null primary key generated always as identity
                , note text not null
                )
            """)

            # create a vectorizer for the table. this should fail
            # language=PostgreSQL
            with pytest.raises(
                psycopg.errors.RaiseException,
                match=".*automatic indexing is not supported without scheduling",
            ):
                cur.execute("""
                select ai.create_vectorizer
                ( 'vec.note3'::regclass
                , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
                , chunking=>ai.chunking_character_text_splitter('note')
                , scheduling=> ai.scheduling_none()
                , indexing=>ai.indexing_hnsw(min_rows=>10, m=>20)
                , grant_to=>null
                , enqueue_existing=>false
                );
                """)

            # create a vectorizer for the table. this should succeed
            # language=PostgreSQL
            cur.execute("""
            select ai.create_vectorizer
            ( 'vec.note3'::regclass
            , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
            , chunking=>ai.chunking_character_text_splitter('note')
            , scheduling=> ai.scheduling_none()
            , indexing=>ai.indexing_none()
            , grant_to=>null
            , enqueue_existing=>false
            );
            """)
            assert True
