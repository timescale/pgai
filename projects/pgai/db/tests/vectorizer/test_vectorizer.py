import json
import os
import subprocess

import psycopg
import pytest
from psycopg.rows import namedtuple_row


def detailed_notice_handler(diag):
    print(f"""
    Severity: {diag.severity}
    Message:  {diag.message_primary}
    Detail:   {diag.message_detail}
    Hint:     {diag.message_hint}
    """)


# skip tests in this module if disabled
enable_vectorizer_tests = os.getenv("ENABLE_VECTORIZER_TESTS")
if enable_vectorizer_tests == "0":
    pytest.skip(allow_module_level=True)


VECTORIZER_ROW = r"""
{
    "id": 1,
    "config": {
        "loading": {
            "config_type": "loading",
            "implementation": "column",
            "retries": 6,
            "column_name": "body"
        },
        "parsing": {
            "config_type": "parsing",
            "implementation": "auto"
        },
        "chunking": {
            "separator": "\n\n",
            "chunk_size": 128,
            "config_type": "chunking",
            "chunk_overlap": 10,
            "implementation": "character_text_splitter",
            "is_separator_regex": false
        },
        "destination": {
            "config_type": "destination",
            "implementation": "table",
            "target_schema": "website",
            "target_table": "blog_embedding_store",
            "view_name": "blog_embedding",
            "view_schema": "website"
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
            "typname": "timestamp with time zone"
        }
    ],
    "queue_table": "_vectorizer_q_1",
    "queue_schema": "ai",
    "name": "website_blog_embedding_store",
    "queue_failed_table": "_vectorizer_q_failed_1",
    "source_table": "blog",
    "trigger_name": "_vectorizer_src_trg_1",
    "source_schema": "website",
    "disabled": false
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
Triggers:
    _vectorizer_src_trg_1 AFTER INSERT OR DELETE OR UPDATE ON website.blog FOR EACH ROW EXECUTE FUNCTION ai._vectorizer_src_trg_1()
    _vectorizer_src_trg_1_truncate AFTER TRUNCATE ON website.blog FOR EACH STATEMENT EXECUTE FUNCTION ai._vectorizer_src_trg_1()
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
 embedding      | vector(768)              |           | not null |                   | main     |             |              | 
Indexes:
    "blog_embedding_store_pkey" PRIMARY KEY, btree (embedding_uuid)
    "blog_embedding_store_title_published_chunk_seq_key" UNIQUE CONSTRAINT, btree (title, published, chunk_seq)
Access method: heap
""".strip()


QUEUE_TABLE = """
                                                 Table "ai._vectorizer_q_1"
       Column        |           Type           | Collation | Nullable | Default | Storage  | Compression | Stats target | Description 
---------------------+--------------------------+-----------+----------+---------+----------+-------------+--------------+-------------
 title               | text                     |           | not null |         | extended |             |              | 
 published           | timestamp with time zone |           | not null |         | plain    |             |              | 
 queued_at           | timestamp with time zone |           | not null | now()   | plain    |             |              | 
 loading_retries     | integer                  |           | not null | 0       | plain    |             |              | 
 loading_retry_after | timestamp with time zone |           |          |         | plain    |             |              | 
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
    cmd = f'''psql -X -d "{db_url("test")}" -c "{cmd}"'''
    proc = subprocess.run(cmd, shell=True, check=True, text=True, capture_output=True)
    return str(proc.stdout).strip()


@pytest.mark.skipif(os.getenv("PG_MAJOR") == "15", reason="does not support pg15")
def test_vectorizer_timescaledb():
    with psycopg.connect(db_url("test")) as con:
        with con.cursor() as cur:
            cur.execute("create extension ai cascade")

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
            , loading => ai.loading_column('body')
            , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
            , chunking=>ai.chunking_character_text_splitter(128, 10)
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

            # Test DELETE trigger
            cur.execute("""
                delete from website.blog 
                where title = 'how to make sandwich'
            """)
            # Verify row was deleted from target table
            cur.execute("""
                select count(*) from website.blog_embedding_store 
                where title = 'how to make sandwich'
            """)
            assert cur.fetchone()[0] == 0

            # Test regular UPDATE (no PK change)
            cur.execute("""
                update website.blog 
                set body = 'updated body'
                where title = 'how to make stir fry'
            """)
            # Verify this caused a queue insert
            cur.execute("""
                select count(*) from ai._vectorizer_q_1
                where title = 'how to make stir fry'
            """)
            assert cur.fetchone()[0] == 1

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

            cur.execute("""
                            INSERT INTO website.blog_embedding_store
                            (title, published, chunk_seq, chunk, embedding)
                            VALUES
                            ('how to make stir fry', '2022-01-06'::timestamptz, 1, 'Chunk of content', array_fill(0.1::float8, ARRAY[768]))
                        """)

            cur.execute("""
                            select count(*) from website.blog_embedding_store 
                            where title = 'how to make stir fry'
                        """)
            assert cur.fetchone()[0] == 1

            # Test UPDATE with PK change
            cur.execute("""
                update website.blog 
                set title = 'how to make better stir fry'
                where title = 'how to make stir fry'
            """)
            # Verify old PK was deleted from target
            cur.execute("""
                select count(*) from website.blog_embedding_store 
                where title = 'how to make stir fry'
            """)
            assert cur.fetchone()[0] == 0
            # Verify new PK was queued
            cur.execute("""
                select count(*) from ai._vectorizer_q_1
                where title = 'how to make better stir fry'
            """)
            assert cur.fetchone()[0] == 1

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
                "select set_config('ai.external_functions_executor_url', 'http://0.0.0.0:8000', false)"
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

            # Test TRUNCATE
            # Insert some data into the target table
            cur.execute("""
                WITH vector_data AS (
                    SELECT 
                        array_fill(0.1::float8, ARRAY[768]) AS vec1,
                        array_fill(0.2::float8, ARRAY[768]) AS vec2,
                        array_fill(0.3::float8, ARRAY[768]) AS vec3
                )
                INSERT INTO website.blog_embedding_store
                (title, published, chunk_seq, chunk, embedding)
                VALUES
                ('how to make better stir fry', NOW(), 1, 'First chunk of content', (SELECT vec1::vector FROM vector_data)),
                ('how to make better stir fry', NOW(), 2, 'Second chunk of content', (SELECT vec2::vector FROM vector_data)),
                ('how to make ramen', NOW(), 1, 'Simple ramen instructions', (SELECT vec3::vector FROM vector_data))
            """)

            # Verify we have data in the target table
            cur.execute("SELECT COUNT(*) FROM website.blog_embedding_store")
            count_before_truncate = cur.fetchone()[0]
            assert (
                count_before_truncate == 3
            ), "Expected 3 rows in target table before truncate test"

            # insert into the source table
            cur.execute("""
                insert into website.blog(title, published, body)
                values
                  ('how to make a better sandwich', '2022-01-06'::timestamptz, 'boil water. cook ramen in the water')
            """)
            # check that the queue has rows
            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer_id,))
            actual = cur.fetchone()[0]
            assert actual > 0

            # Perform TRUNCATE on source table
            cur.execute("truncate table website.blog")

            # Verify target table was also truncated
            cur.execute("select count(*) from website.blog_embedding_store")
            count_after_truncate = cur.fetchone()[0]
            assert (
                count_after_truncate == 0
            ), "Target table should be empty after source table truncate"

            # check that the queue has 0 rows
            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer_id,))
            actual = cur.fetchone()[0]
            assert actual == 0

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


@pytest.mark.skipif(os.getenv("PG_MAJOR") == "15", reason="does not support pg15")
def test_drop_vectorizer():
    with psycopg.connect(
        db_url("test"), autocommit=True, row_factory=namedtuple_row
    ) as con:
        with con.cursor() as cur:
            cur.execute("create extension if not exists timescaledb")
            # need ai extension for timescaledb scheduling
            cur.execute("create extension if not exists ai cascade")
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
            , loading => ai.loading_column('content')
            , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
            , chunking=>ai.chunking_character_text_splitter(128, 10)
            , scheduling=>ai.scheduling_timescaledb()
            , grant_to=>null
            );
            """)
            vectorizer_id = cur.fetchone()[0]

            cur.execute("select * from ai.vectorizer where id = %s", (vectorizer_id,))
            vectorizer = cur.fetchone()

            # does the target table exist? (it should)
            cur.execute(
                f"select to_regclass('{vectorizer.config['destination']['target_schema']}.{vectorizer.config['destination']['target_table']}') is not null"
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
                f"select to_regclass('{vectorizer.config['destination']['view_schema']}.{vectorizer.config['destination']['view_name']}') is not null"
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
                f"select to_regclass('{vectorizer.config['destination']['target_schema']}.{vectorizer.config['destination']['target_table']}') is not null"
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
                f"select to_regclass('{vectorizer.config['destination']['view_schema']}.{vectorizer.config['destination']['view_name']}') is not null"
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


@pytest.mark.skipif(os.getenv("PG_MAJOR") == "15", reason="does not support pg15")
def test_drop_all_vectorizer():
    with psycopg.connect(
        db_url("test"), autocommit=True, row_factory=namedtuple_row
    ) as con:
        with con.cursor() as cur:
            cur.execute("create extension if not exists timescaledb")
            # need ai extension for timescaledb scheduling
            cur.execute("create extension if not exists ai cascade")
            cur.execute("drop table if exists drop_me")
            cur.execute("""
                create table drop_me
                ( id serial not null primary key
                , content text not null
                )
            """)
            cur.execute("""
                insert into drop_me(content)
                values ('put it on a hot grill')
            """)

            # create a vectorizer for the blog table
            # language=PostgreSQL
            cur.execute("""
            select ai.create_vectorizer
            ( 'drop_me'::regclass
            , loading => ai.loading_column('content')
            , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
            , chunking=>ai.chunking_character_text_splitter(128, 10)
            , scheduling=>ai.scheduling_timescaledb()
            , grant_to=>null
            );
            """)
            vectorizer_id = cur.fetchone()[0]

            cur.execute("select * from ai.vectorizer where id = %s", (vectorizer_id,))
            vectorizer = cur.fetchone()

            # does the target table exist? (it should)
            cur.execute(
                f"select to_regclass('{vectorizer.config['destination']['target_schema']}.{vectorizer.config['destination']['target_table']}') is not null"
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
                f"select to_regclass('{vectorizer.config['destination']['view_schema']}.{vectorizer.config['destination']['view_name']}') is not null"
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

            # drop the vectorizer with drop_all=>true
            cur.execute(
                "select ai.drop_vectorizer(%s, drop_all=>true)", (vectorizer_id,)
            )

            # does the target table exist? (it should NOT)
            cur.execute(
                f"select to_regclass('{vectorizer.config['destination']['target_schema']}.{vectorizer.config['destination']['target_table']}') is not null"
            )
            actual = cur.fetchone()[0]
            assert actual is False

            # does the queue table exist? (it should NOT)
            cur.execute(
                f"select to_regclass('{vectorizer.queue_schema}.{vectorizer.queue_table}') is not null"
            )
            actual = cur.fetchone()[0]
            assert actual is False

            # does the view exist? (it should NOT)
            cur.execute(
                f"select to_regclass('{vectorizer.config['destination']['view_schema']}.{vectorizer.config['destination']['view_name']}') is not null"
            )
            actual = cur.fetchone()[0]
            assert actual is False

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
    pytest.skip("not working right now")
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
            , loading => ai.loading_column('content')
            , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
            , chunking=>ai.chunking_character_text_splitter(128, 10)
            , scheduling=>ai.scheduling_timescaledb()
            , grant_to=>null
            );
            """)
            vectorizer_id = cur.fetchone()[0]

            cur.execute("select * from ai.vectorizer where id = %s", (vectorizer_id,))
            vectorizer = cur.fetchone()

            # does the target table exist? (it should)
            cur.execute(
                f"select to_regclass('{vectorizer.config['destination']['target_schema']}.{vectorizer.config['destination']['target_table']}') is not null"
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
                f"select to_regclass('{vectorizer.config['destination']['view_schema']}.{vectorizer.config['destination']['view_name']}') is not null"
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

            # does the target table exist? (it should NOT)
            cur.execute(
                f"select to_regclass('{vectorizer.config['destination']['target_schema']}.{vectorizer.config['destination']['target_table']}') is not null"
            )
            actual = cur.fetchone()[0]
            assert actual is False

            # does the queue table exist? (it should not b/c of cascade)
            cur.execute(
                f"select to_regclass('{vectorizer.queue_schema}.{vectorizer.queue_table}') is not null"
            )
            actual = cur.fetchone()[0]
            assert actual is False

            # does the view exist? (it should not)
            cur.execute(
                f"select to_regclass('{vectorizer.config['destination']['view_schema']}.{vectorizer.config['destination']['view_name']}') is not null"
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


def test_drop_source_no_row():
    pytest.skip("not working right now")
    with psycopg.connect(
        db_url("test"), autocommit=True, row_factory=namedtuple_row
    ) as con:
        with con.cursor() as cur:
            cur.execute("create extension if not exists ai cascade")
            cur.execute("create extension if not exists timescaledb")
            cur.execute("drop table if exists public.drop_no_row")
            cur.execute("""
                create table public.drop_no_row
                ( id serial not null primary key
                , content text not null
                )
            """)

            # create a vectorizer for the table
            # language=PostgreSQL
            cur.execute("""
            select ai.create_vectorizer
            ( 'public.drop_no_row'::regclass
            , loading => ai.loading_column('content')
            , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
            , chunking=>ai.chunking_character_text_splitter(128, 10)
            , scheduling=>ai.scheduling_timescaledb()
            , grant_to=>null
            );
            """)
            vectorizer_id = cur.fetchone()[0]

            cur.execute("select * from ai.vectorizer where id = %s", (vectorizer_id,))
            vectorizer = cur.fetchone()

            # does the target table exist? (it should)
            cur.execute(
                f"select to_regclass('{vectorizer.config['destination']['target_schema']}.{vectorizer.config['destination']['target_table']}') is not null"
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
                f"select to_regclass('{vectorizer.config['destination']['view_schema']}.{vectorizer.config['destination']['view_name']}') is not null"
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

            # delete the vectorizer row !!!!
            # this prevents the event trigger from working since it can't look up the vectorizer
            cur.execute("delete from ai.vectorizer where id = %s", (vectorizer_id,))
            assert cur.rowcount == 1

            # drop the source table with cascade
            cur.execute(
                f"drop table {vectorizer.source_schema}.{vectorizer.source_table} cascade"
            )

            # does the target table exist? (it should NOT)
            cur.execute(
                f"select to_regclass('{vectorizer.config['destination']['target_schema']}.{vectorizer.config['destination']['target_table']}') is not null"
            )
            actual = cur.fetchone()[0]
            assert actual is False

            # does the queue table exist? (it should not b/c of cascade)
            cur.execute(
                f"select to_regclass('{vectorizer.queue_schema}.{vectorizer.queue_table}') is not null"
            )
            actual = cur.fetchone()[0]
            assert actual is False

            # does the view exist? (it should not)
            cur.execute(
                f"select to_regclass('{vectorizer.config['destination']['view_schema']}.{vectorizer.config['destination']['view_name']}') is not null"
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

            # does the func that backed the trigger exist? (it SHOULD)
            # we didn't have the vectorizer row to look it up
            cur.execute(
                """
                select count(*)
                from pg_proc
                where oid = %s
            """,
                (pg_proc_oid,),
            )
            actual = cur.fetchone()[0]
            assert actual == 1

            # does the timescaledb job exist? (it SHOULD)
            # we didn't have the vectorizer row to look it up
            cur.execute(
                """
                select count(*)
                from timescaledb_information.jobs
                where job_id = %s
            """,
                (vectorizer.config["scheduling"]["job_id"],),
            )
            actual = cur.fetchone()[0]
            assert actual == 1


def index_creation_tester(cur: psycopg.Cursor, vectorizer_id: int) -> None:
    cur.execute("select * from ai.vectorizer where id = %s", (vectorizer_id,))
    vectorizer = cur.fetchone()

    # make sure the index does NOT exist
    cur.execute(
        """
                select ai._vectorizer_vector_index_exists(v.config->'destination'->>'target_schema', v.config->'destination'->>'target_table', v.config->'indexing')
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
                select ai._vectorizer_vector_index_exists(v.config->'destination'->>'target_schema', v.config->'destination'->>'target_table', v.config->'indexing')
                from ai.vectorizer v
                where v.id = %s
            """,
        (vectorizer_id,),
    )
    actual = cur.fetchone()[0]
    assert actual is False

    # insert 5 rows into the target
    cur.execute(f"""
                insert into {vectorizer.config['destination']['target_schema']}.{vectorizer.config['destination']['target_table']}
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
                select ai._vectorizer_vector_index_exists(v.config->'destination'->>'target_schema', v.config->'destination'->>'target_table', v.config->'indexing')
                from ai.vectorizer v
                where v.id = %s
            """,
        (vectorizer_id,),
    )
    actual = cur.fetchone()[0]
    assert actual is False

    # insert 5 rows into the target
    cur.execute(f"""
                insert into {vectorizer.config['destination']['target_schema']}.{vectorizer.config['destination']['target_table']}
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
                select ai._vectorizer_vector_index_exists(v.config->'destination'->>'target_schema', v.config->'destination'->>'target_table', v.config->'indexing')
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
                select ai._vectorizer_vector_index_exists(v.config->'destination'->>'target_schema', v.config->'destination'->>'target_table', v.config->'indexing')
                from ai.vectorizer v
                where v.id = %s
            """,
        (vectorizer_id,),
    )
    actual = cur.fetchone()[0]
    assert actual is True


@pytest.mark.skipif(os.getenv("PG_MAJOR") == "15", reason="does not support pg15")
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
            , loading => ai.loading_column('note')
            , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
            , chunking=>ai.chunking_character_text_splitter()
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


@pytest.mark.skipif(os.getenv("PG_MAJOR") == "15", reason="does not support pg15")
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
            , loading => ai.loading_column('note')
            , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
            , chunking=>ai.chunking_character_text_splitter()
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


@pytest.mark.skipif(os.getenv("PG_MAJOR") == "15", reason="does not support pg15")
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
            cur.execute("create extension if not exists timescaledb")
            # need ai extension for timescaledb scheduling
            cur.execute("create extension if not exists ai cascade")
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
            , loading => ai.loading_column('note')
            , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
            , chunking=>ai.chunking_character_text_splitter()
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
                        select ai._vectorizer_vector_index_exists(v.config->'destination'->>'target_schema', v.config->'destination'->>'target_table', v.config->'indexing')
                        from ai.vectorizer v
                        where v.id = %s
                    """,
                (vectorizer_id,),
            )
            actual = cur.fetchone()[0]
            assert actual is False

            # insert 10 rows into the target
            cur.execute(f"""
                        insert into {vectorizer.config['destination']['target_schema']}.{vectorizer.config['destination']['target_table']}
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
                        select ai._vectorizer_create_vector_index(v.config->'destination'->>'target_schema', v.config->'destination'->>'target_table', v.config->'indexing')
                        from ai.vectorizer v
                        where v.id = %s
                        """,
                        (vectorizer_id,),
                    )
                    # hold the transaction open
                    # try to explicitly create the index on the other connection
                    cur.execute(
                        """
                        select ai._vectorizer_create_vector_index(v.config->'destination'->>'target_schema', v.config->'destination'->>'target_table', v.config->'indexing')
                        from ai.vectorizer v
                        where v.id = %s
                        """,
                        (vectorizer_id,),
                    )
                    con2.commit()

            # make sure the index DOES exist (min_rows = 10)
            cur.execute(
                """
                        select ai._vectorizer_vector_index_exists(v.config->'destination'->>'target_schema', v.config->'destination'->>'target_table', v.config->'indexing')
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
                on (n.nspname operator(pg_catalog.=) (v.config->'destination'->>'target_schema')
                and k.relname operator(pg_catalog.=) (v.config->'destination'->>'target_table'))
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
            , loading => ai.loading_column('note')
            , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
            , chunking=>ai.chunking_character_text_splitter()
            , scheduling=>ai.scheduling_none()
            , indexing=>ai.indexing_none()
            , grant_to=>null
            , enqueue_existing=>false
            );
            """)

            # try to create another one, fail on view_name / destination collision
            # language=PostgreSQL
            with pytest.raises(
                psycopg.errors.DuplicateObject,
                match=".*specify an alternate destination or view_name explicitly*",
            ):
                cur.execute("""
                select ai.create_vectorizer
                ( 'vec.note4'::regclass
                , name => 'dont_collide_on_name'
                , loading => ai.loading_column('note')
                , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
                , chunking=>ai.chunking_character_text_splitter()
                , scheduling=>ai.scheduling_none()
                , indexing=>ai.indexing_none()
                , grant_to=>null
                , enqueue_existing=>false
                );
                """)

            # try to create another one, fail on target_table name collision
            # language=PostgreSQL
            with pytest.raises(
                psycopg.errors.DuplicateObject,
                match=".*specify an alternate destination or target_table explicitly*",
            ):
                cur.execute("""
                select ai.create_vectorizer
                ( 'vec.note4'::regclass
                , name => 'dont_collide_on_name'
                , loading => ai.loading_column('note')
                , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
                , chunking=>ai.chunking_character_text_splitter()
                , scheduling=>ai.scheduling_none()
                , indexing=>ai.indexing_none()
                , grant_to=>null
                , enqueue_existing=>false
                , destination=>ai.destination_table(view_schema=>'ai', view_name=>'note4_embedding2')
                );
                """)

            # try to create another one, fail on queue_table name collision
            # language=PostgreSQL
            with pytest.raises(
                psycopg.errors.DuplicateObject,
                match=".*specify an alternate queue_table explicitly*",
            ):
                cur.execute("""
                select ai.create_vectorizer
                ( 'vec.note4'::regclass
                , name => 'dont_collide_on_name'
                , loading => ai.loading_column('note')
                , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
                , chunking=>ai.chunking_character_text_splitter()
                , scheduling=>ai.scheduling_none()
                , indexing=>ai.indexing_none()
                , grant_to=>null
                , enqueue_existing=>false
                , destination=>ai.destination_table(view_schema=>'ai',
                                                      view_name=>'note4_embedding2',
                                                      target_schema=>'vec',
                                                      target_table=>'note4_embedding_store2')
                , queue_schema=>'ai'
                , queue_table=>'_vectorizer_q_1'
                );
                """)

            # try to create another one, this should work
            # language=PostgreSQL
            cur.execute("""
            select ai.create_vectorizer
            ( 'vec.note4'::regclass
            , loading => ai.loading_column('note')
            , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
            , chunking=>ai.chunking_character_text_splitter()
            , scheduling=>ai.scheduling_none()
            , indexing=>ai.indexing_none()
            , grant_to=>null
            , enqueue_existing=>false
            , destination=>ai.destination_table(target_schema=>'vec',
                                                  target_table=>'note4_embedding_store2',
                                                  view_schema=>'vec',
                                                  view_name=>'note4_embedding2')
            , queue_schema=>'ai'
            , queue_table=>'this_is_a_queue_table'
            );
            """)
            vectorizer_id = cur.fetchone()[0]
            cur.execute("select * from ai.vectorizer where id = %s", (vectorizer_id,))
            vectorizer = cur.fetchone()
            assert vectorizer.config["destination"]["target_schema"] == "vec"
            assert (
                vectorizer.config["destination"]["target_table"]
                == "note4_embedding_store2"
            )
            assert vectorizer.queue_schema == "ai"
            assert vectorizer.queue_table == "this_is_a_queue_table"
            assert vectorizer.config["destination"]["view_schema"] == "vec"
            assert vectorizer.config["destination"]["view_name"] == "note4_embedding2"
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
            , loading => ai.loading_column('note')
            , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
            , chunking=>ai.chunking_character_text_splitter()
            , scheduling=>ai.scheduling_none()
            , indexing=>ai.indexing_none()
            , grant_to=>null
            , enqueue_existing=>false
            , destination=>ai.destination_table(destination=>'fernando')
            );
            """)
            vectorizer_id = cur.fetchone()[0]
            cur.execute("select * from ai.vectorizer where id = %s", (vectorizer_id,))
            vectorizer = cur.fetchone()
            assert vectorizer.config["destination"]["target_schema"] == "vec"
            assert vectorizer.config["destination"]["target_table"] == "fernando_store"
            assert vectorizer.queue_schema == "ai"
            assert vectorizer.queue_table == f"_vectorizer_q_{vectorizer.id}"
            assert vectorizer.config["destination"]["view_schema"] == "vec"
            assert vectorizer.config["destination"]["view_name"] == "fernando"
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
                , loading => ai.loading_column('note')
                , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
                , chunking=>ai.chunking_character_text_splitter()
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
            , loading => ai.loading_column('note')
            , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
            , chunking=>ai.chunking_character_text_splitter()
            , scheduling=> ai.scheduling_none()
            , indexing=>ai.indexing_none()
            , grant_to=>null
            , enqueue_existing=>false
            );
            """)
            assert True


def test_queue_pending():
    with psycopg.connect(
        db_url("test"), autocommit=True, row_factory=namedtuple_row
    ) as con:
        with con.cursor() as cur:
            cur.execute("create extension if not exists timescaledb")
            cur.execute("create schema if not exists vec")
            cur.execute("drop table if exists vec.note5")
            cur.execute("""
                create table vec.note5
                ( id bigint not null primary key generated always as identity
                , note text not null
                )
            """)

            # create a vectorizer for the table
            # language=PostgreSQL
            cur.execute("""
            select ai.create_vectorizer
            ( 'vec.note5'::regclass
            , loading => ai.loading_column('note')
            , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
            , chunking=>ai.chunking_character_text_splitter()
            , scheduling=> ai.scheduling_none()
            , indexing=>ai.indexing_none()
            , grant_to=>null
            , enqueue_existing=>false
            );
            """)
            vectorizer_id = cur.fetchone()[0]

            cur.execute("select * from ai.vectorizer where id = %s", (vectorizer_id,))
            vectorizer = cur.fetchone()

            # insert 1001 rows into the queue
            cur.execute(f"""
            insert into {vectorizer.queue_schema}.{vectorizer.queue_table} (id)
            select x from generate_series(1, 10001) x
            """)

            # an exact count should yield 10001
            cur.execute(
                "select ai.vectorizer_queue_pending(%s, true)", (vectorizer_id,)
            )
            assert cur.fetchone()[0] == 10001

            # a non-exact count should yield 9223372036854775807
            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer_id,))
            assert cur.fetchone()[0] == 9223372036854775807


def test_grant_to_public():
    with psycopg.connect(
        db_url("test"), autocommit=True, row_factory=namedtuple_row
    ) as con:
        with con.cursor() as cur:
            cur.execute("create extension if not exists timescaledb")
            cur.execute("create schema if not exists vec")
            cur.execute("drop table if exists vec.note6")
            cur.execute("""
                create table vec.note6
                ( id bigint not null primary key generated always as identity
                , note text not null
                )
            """)

            # create a vectorizer for the table
            # language=PostgreSQL
            cur.execute("""
            select ai.create_vectorizer
            ( 'vec.note6'::regclass
            , loading => ai.loading_column('note')
            , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
            , chunking=>ai.chunking_character_text_splitter()
            , scheduling=> ai.scheduling_none()
            , indexing=>ai.indexing_none()
            , grant_to=>ai.grant_to('public')
            , enqueue_existing=>false
            );
            """)
            vectorizer_id = cur.fetchone()[0]

            cur.execute("select * from ai.vectorizer where id = %s", (vectorizer_id,))
            vectorizer = cur.fetchone()

            cur.execute(f"""
                select has_table_privilege
                ( 'public'
                , '{vectorizer.queue_schema}.{vectorizer.queue_table}'
                , 'select'
                )""")
            assert cur.fetchone()[0]

            cur.execute(f"""
                select has_table_privilege
                ( 'public'
                , '{vectorizer.config['destination']['target_schema']}.{vectorizer.config['destination']['target_table']}'
                , 'select'
                )""")
            assert cur.fetchone()[0]


def create_user(cur: psycopg.Cursor, user: str) -> None:
    cur.execute(
        """
        select count(*) > 0
        from pg_catalog.pg_roles
        where rolname = %s
    """,
        (user,),
    )
    if not cur.fetchone()[0]:
        cur.execute(f"create user {user}")


def test_create_vectorizer_privs():
    with psycopg.connect(db_url("postgres")) as con:
        with con.cursor() as cur:
            create_user(cur, "jimmy")
            cur.execute("grant create on schema public to jimmy")
            cur.execute("select ai.grant_vectorizer_usage('jimmy', admin=>false)")
            create_user(cur, "greg")
            cur.execute("select ai.grant_vectorizer_usage('greg', admin=>false)")

    # jimmy owns the source table
    with psycopg.connect(db_url("jimmy")) as con:
        with con.cursor() as cur:
            cur.execute("""
            create table priv_test
            ( id int not null primary key generated always as identity
            , foo text
            , bar text
            )
            """)

    # greg does not own the table, does not own the database, and is not superuser
    # this should fail
    with psycopg.connect(db_url("greg")) as con:
        with con.cursor() as cur:
            with pytest.raises(
                psycopg.errors.RaiseException,
                match=".*only a superuser or the owner of the source table may create a vectorizer on it",
            ):
                cur.execute("""
                select ai.create_vectorizer
                ( 'priv_test'::regclass
                , loading => ai.loading_column('foo')
                , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
                , chunking=>ai.chunking_character_text_splitter()
                , scheduling=>ai.scheduling_none()
                , indexing=>ai.indexing_none()
                , grant_to=>null
                );
                """)

    # test owns the database, but not the table, and is not superuser
    # this should not work
    with psycopg.connect(db_url("test")) as con:
        with con.cursor() as cur:
            with pytest.raises(
                psycopg.errors.RaiseException,
                match=".*only a superuser or the owner of the source table may create a vectorizer on it",
            ):
                cur.execute("""
                select ai.create_vectorizer
                ( 'priv_test'::regclass
                , loading => ai.loading_column('foo')
                , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
                , chunking=>ai.chunking_character_text_splitter()
                , scheduling=>ai.scheduling_none()
                , indexing=>ai.indexing_none()
                , grant_to=>null
                );
                """)

    # jimmy owns the table. this should work
    with psycopg.connect(db_url("jimmy")) as con:
        with con.cursor() as cur:
            cur.execute("""
            select ai.create_vectorizer
            ( 'priv_test'::regclass
            , loading => ai.loading_column('foo')
            , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
            , chunking=>ai.chunking_character_text_splitter()
            , scheduling=>ai.scheduling_none()
            , indexing=>ai.indexing_none()
            , grant_to=>null
            );
            """)

    # postgres is superuser. this should work
    with psycopg.connect(db_url("postgres")) as con:
        with con.cursor() as cur:
            cur.execute("""
            select ai.create_vectorizer
            ( 'priv_test'::regclass
            , loading => ai.loading_column('foo')
            , destination=>ai.destination_table(destination=>'red_balloon')
            , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
            , chunking=>ai.chunking_character_text_splitter()
            , scheduling=>ai.scheduling_none()
            , indexing=>ai.indexing_none()
            , grant_to=>null
            );
            """)


def test_vectorizer_bytea():
    with psycopg.connect(
        db_url("test"), autocommit=True, row_factory=namedtuple_row
    ) as con:
        with con.cursor() as cur:
            cur.execute("create extension if not exists timescaledb")
            cur.execute("create schema if not exists vec")
            cur.execute("drop table if exists vec.doc_bytea")
            cur.execute("""
                create table vec.doc_bytea
                ( id bigint not null primary key generated always as identity
                , content bytea not null
                )
            """)

            # Insert a sample PDF as bytea
            cur.execute("""
                insert into vec.doc_bytea(content)
                values (decode('255044462D312E340A25', 'hex'))  -- Start of PDF file magic bytes
            """)

            # Create a vectorizer for the bytea column
            cur.execute("""
            select ai.create_vectorizer
            ( 'vec.doc_bytea'::regclass
            , loading => ai.loading_column('content')
            , embedding => ai.embedding_openai('text-embedding-3-small', 3)
            , chunking => ai.chunking_character_text_splitter()
            , scheduling => ai.scheduling_none()
            , indexing => ai.indexing_none()
            , grant_to => null
            , enqueue_existing => false
            );
            """)
            vectorizer_id = cur.fetchone()[0]

            # Verify vectorizer was created
            cur.execute("select * from ai.vectorizer where id = %s", (vectorizer_id,))
            vectorizer = cur.fetchone()
            assert vectorizer is not None
            assert vectorizer.config["loading"]["column_name"] == "content"
            assert vectorizer.config["parsing"]["implementation"] == "auto"


def test_vectorizer_document_loading_pymupdf():
    with psycopg.connect(
        db_url("test"), autocommit=True, row_factory=namedtuple_row
    ) as con:
        with con.cursor() as cur:
            cur.execute("create extension if not exists timescaledb")
            cur.execute("create schema if not exists vec")
            cur.execute("drop table if exists vec.doc_url_pymupdf")
            cur.execute("""
                create table vec.doc_url_pymupdf
                ( id bigint not null primary key generated always as identity
                , url text not null
                )
            """)

            # Create vectorizer with document loading and pymupdf - should work
            cur.execute("""
            select ai.create_vectorizer
            ( 'vec.doc_url_pymupdf'::regclass
            , loading => ai.loading_uri('url')
            , parsing => ai.parsing_pymupdf()
            , embedding => ai.embedding_openai('text-embedding-3-small', 3)
            , chunking => ai.chunking_character_text_splitter()
            , scheduling => ai.scheduling_none()
            , indexing => ai.indexing_none()
            , grant_to => null
            , enqueue_existing => false
            );
            """)
            vectorizer_id = cur.fetchone()[0]

            # Verify vectorizer was created with correct configuration
            cur.execute("select * from ai.vectorizer where id = %s", (vectorizer_id,))
            vectorizer = cur.fetchone()
            assert vectorizer is not None
            assert vectorizer.config["loading"]["column_name"] == "url"
            assert vectorizer.config["loading"]["implementation"] == "uri"
            assert vectorizer.config["parsing"]["implementation"] == "pymupdf"


def test_vectorizer_bytea_parsing_none_fails():
    with psycopg.connect(
        db_url("test"), autocommit=True, row_factory=namedtuple_row
    ) as con:
        with con.cursor() as cur:
            cur.execute("create extension if not exists timescaledb")
            cur.execute("create schema if not exists vec")
            cur.execute("drop table if exists vec.doc_bytea_fail")
            cur.execute("""
                create table vec.doc_bytea_fail
                ( id bigint not null primary key generated always as identity
                , content bytea not null
                )
            """)

            # Attempt to create vectorizer with parsing_none on bytea - should fail
            with pytest.raises(
                psycopg.errors.RaiseException,
                match=".*cannot use parsing_none with bytea columns.*",
            ):
                cur.execute("""
                select ai.create_vectorizer
                ( 'vec.doc_bytea_fail'::regclass
                , loading => ai.loading_column('content')
                , parsing => ai.parsing_none()
                , embedding => ai.embedding_openai('text-embedding-3-small', 3)
                , chunking => ai.chunking_character_text_splitter()
                , scheduling => ai.scheduling_none()
                , indexing => ai.indexing_none()
                , grant_to => null
                , enqueue_existing => false
                );
                """)


def test_vectorizer_uri_loading_parsing_none_is_allowed():
    with psycopg.connect(
        db_url("test"), autocommit=True, row_factory=namedtuple_row
    ) as con:
        with con.cursor() as cur:
            cur.execute("create schema if not exists vec")
            cur.execute("drop table if exists vec.doc_url_parsing_none")
            cur.execute("""
                create table vec.doc_url_parsing_none
                ( id bigint not null primary key generated always as identity
                , url text not null
                )
            """)

            # Vectorizer with uri loading and parsing_none should be allowed since
            # the user might want to load a raw text file (not requiring any parsing)
            cur.execute("""
            select ai.create_vectorizer
            ( 'vec.doc_url_parsing_none'::regclass
            , loading => ai.loading_uri('url')
            , parsing => ai.parsing_none()
            , embedding => ai.embedding_openai('text-embedding-3-small', 3)
            , chunking => ai.chunking_character_text_splitter()
            , scheduling => ai.scheduling_none()
            , indexing => ai.indexing_none()
            , grant_to => null
            , enqueue_existing => false
            );
            """)

            vectorizer_id = cur.fetchone()[0]

            # Verify vectorizer was created with correct configuration
            cur.execute("select * from ai.vectorizer where id = %s", (vectorizer_id,))
            vectorizer = cur.fetchone()
            assert vectorizer is not None
            assert vectorizer.config["loading"]["column_name"] == "url"
            assert vectorizer.config["loading"]["implementation"] == "uri"
            assert vectorizer.config["parsing"]["implementation"] == "none"


def test_vectorizer_text_pymupdf_fails():
    with psycopg.connect(
        db_url("test"), autocommit=True, row_factory=namedtuple_row
    ) as con:
        with con.cursor() as cur:
            cur.execute("create extension if not exists timescaledb")
            cur.execute("create schema if not exists vec")

            # Test each text type
            text_types = ["text", "varchar", "char(10)", "character varying"]

            for text_type in text_types:
                # Replace multiple special characters and spaces with underscores
                sanitized_type = (
                    text_type.replace(" ", "_")
                    .replace("(", "_")
                    .replace(")", "")
                    .replace(",", "_")
                )
                # Remove any double underscores that might have been created
                sanitized_type = "_".join(filter(None, sanitized_type.split("_")))
                table_name = f"vec.text_pymupdf_fail_{sanitized_type}"
                cur.execute(f"drop table if exists {table_name}")
                cur.execute(f"""
                    create table {table_name}
                    ( id bigint not null primary key generated always as identity
                    , content {text_type} not null
                    )
                """)

                # Attempt to create vectorizer with pymupdf on text column - should fail
                with pytest.raises(
                    psycopg.errors.RaiseException,
                    match="parsing_pymupdf must be used with a bytea column.*",
                ):
                    cur.execute(f"""
                    select ai.create_vectorizer
                    ( '{table_name}'::regclass
                    , loading => ai.loading_column('content')
                    , parsing => ai.parsing_pymupdf()
                    , embedding => ai.embedding_openai('text-embedding-3-small', 3)
                    , chunking => ai.chunking_character_text_splitter()
                    , scheduling => ai.scheduling_none()
                    , indexing => ai.indexing_none()
                    , grant_to => null
                    , enqueue_existing => false
                    );
                    """)


def test_weird_primary_key():
    # Test multi-column primary keys with "interesting" data types.
    # Using format_type() instead of pg_type.typname is important
    # because format_type() supports these "interesting" types.
    # "Interesting" data types include arrays, ones with multi-word
    # names, domains, ones defined in "non-standard" schemas, etc.
    # This test also ensures that multi-column primary keys are
    # handled correctly in the creation of the queue, trigger,
    # target, and view. We also test the usage of the trigger and
    # queue in the context of this "weird" primary key
    with psycopg.connect(
        db_url("test"), autocommit=True, row_factory=namedtuple_row
    ) as con:
        with con.cursor() as cur:
            cur.execute("create extension if not exists timescaledb")
            cur.execute("create schema if not exists vec")
            cur.execute("drop domain if exists vec.code cascade")
            cur.execute("create domain vec.code as varchar(3)")
            cur.execute("drop table if exists vec.weird")
            cur.execute("""
                create table vec.weird
                ( a text[] not null
                , b vec.code not null
                , c timestamp with time zone not null
                , d tstzrange not null
                , note text not null
                , primary key (a, b, c, d)
                )
            """)

            # create a vectorizer for the table
            # language=PostgreSQL
            cur.execute("""
            select ai.create_vectorizer
            ( 'vec.weird'::regclass
            , loading=>ai.loading_column('note')
            , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
            , chunking=>ai.chunking_character_text_splitter()
            , scheduling=> ai.scheduling_none()
            , indexing=>ai.indexing_none()
            , grant_to=>ai.grant_to('public')
            , enqueue_existing=>false
            );
            """)
            vectorizer_id = cur.fetchone()[0]

            # insert 7 rows into the source and see if the trigger works
            cur.execute("""
                insert into vec.weird(a, b, c, d, note)
                select
                  array['larry', 'moe', 'curly']
                , 'xyz'
                , t
                , tstzrange(t, t + interval '1d', '[)')
                , 'if two witches watch two watches, which witch watches which watch'
                from generate_series('2025-01-06'::timestamptz, '2025-01-12'::timestamptz, interval '1d') t
                """)

            # check that the queue has 7 rows
            cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer_id,))
            actual = cur.fetchone()[0]
            assert actual == 7


@pytest.mark.skipif(os.getenv("PG_MAJOR") == "15", reason="does not support pg15")
def test_install_ai_extension_before_library():
    with psycopg.connect(db_url("test")) as con:
        with con.cursor() as cur:
            cur.execute("drop schema if exists ai cascade")
            cur.execute("create extension ai cascade")

    import pgai

    pgai.install(db_url("test"))


@pytest.mark.skipif(os.getenv("PG_MAJOR") == "15", reason="does not support pg15")
def test_install_library_before_ai_extension():
    with psycopg.connect(db_url("test")) as con:
        with con.cursor() as cur:
            cur.execute("drop schema if exists ai cascade")

    import pgai

    pgai.install(db_url("test"))

    with psycopg.connect(db_url("test")) as con:
        with con.cursor() as cur:
            cur.execute("create extension ai cascade")
