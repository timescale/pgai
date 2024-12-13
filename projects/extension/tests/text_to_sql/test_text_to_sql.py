import os
import subprocess
from pathlib import Path

import pytest
import psycopg
from psycopg.rows import namedtuple_row

# skip tests in this module if disabled
enable_text_to_sql_tests = os.getenv("ENABLE_TEXT_TO_SQL_TESTS")
if enable_text_to_sql_tests == "0":
    pytest.skip(allow_module_level=True)


def db_url(user: str, dbname: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/{dbname}"


def where_am_i() -> str:
    if "WHERE_AM_I" in os.environ and os.environ["WHERE_AM_I"] == "docker":
        return "docker"
    return "host"


def docker_dir() -> str:
    return "/pgai/tests/text_to_sql"


def host_dir() -> Path:
    return Path(__file__).parent.absolute()


def does_test_user_exist(cur: psycopg.Cursor) -> bool:
    cur.execute("""
        select count(*) > 0
        from pg_catalog.pg_roles
        where rolname = 'test'
    """)
    return cur.fetchone()[0]


def create_test_user(cur: psycopg.Cursor) -> None:
    if not does_test_user_exist(cur):
        cur.execute("create user test password 'test'")


def set_up_test_db(dbname: str) -> None:
    # create a test user and test database owned by the test user
    with psycopg.connect(
        "postgres://postgres@127.0.0.1:5432/postgres", autocommit=True
    ) as con:
        with con.cursor() as cur:
            create_test_user(cur)
            cur.execute(f"drop database if exists {dbname} with (force)")
            cur.execute(f"create database {dbname} owner test")
    # use the test user to create the extension in the text_to_sql database
    with psycopg.connect(f"postgres://test@127.0.0.1:5432/{dbname}") as con:
        with con.cursor() as cur:
            # turn on the feature flag for text_to_sql
            cur.execute(
                "select set_config('ai.enable_feature_flag_text_to_sql', 'true', false)"
            )
            cur.execute("create extension ai cascade")


def snapshot_descriptions(dbname: str, name: str) -> None:
    host_dir().joinpath(f"{name}.actual").unlink(missing_ok=True)
    cmd = " ".join(
        [
            "psql",
            f'''-d "{db_url("test", dbname)}"''',
            "-v ON_ERROR_STOP=1",
            "-X",
            f"-o {docker_dir()}/{name}.actual",
            '-c "select objtype, objnames, objargs, description from ai.semantic_catalog_obj order by 1,2,3"',
        ]
    )
    if where_am_i() != "docker":
        cmd = f"docker exec -w {docker_dir()} pgai-ext {cmd}"
    subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))


def file_contents(name: str) -> str:
    return host_dir().joinpath(f"{name}").read_text()


def test_event_triggers():
    set_up_test_db("text_to_sql_1")
    with psycopg.connect(db_url("test", "text_to_sql_1")) as con:
        with con.cursor() as cur:
            cur.execute("""
            create table bob
            ( id int not null primary key
            , foo text not null
            , bar timestamptz not null default now()
            );

            create view bobby as
            select * from bob;

            create function life(x int) returns int
            as $func$select 42$func$ language sql;
            """)

            # 0 set descriptions
            cur.execute("""
            -- table
            select ai.set_description('bob', 'this is a comment about the bob table');
            select ai.set_column_description('bob', 'id', 'this is a comment about the id column');
            select ai.set_column_description('bob', 'foo', 'this is a comment about the foo column');
            select ai.set_column_description('bob', 'bar', 'this is a comment about the bar column');

            -- view
            select ai.set_description('bobby', 'this is a comment about the bob table');
            select ai.set_column_description('bobby', 'id', 'this is a comment about the id column');
            select ai.set_column_description('bobby', 'foo', 'this is a comment about the foo column');
            select ai.set_column_description('bobby', 'bar', 'this is a comment about the bar column');

            -- function
            select ai.set_function_description('life'::regproc, 'this is a comment about the life function');
            """)
            con.commit()
            snapshot_descriptions("text_to_sql_1", "0")
            actual = file_contents("0.actual")
            expected = file_contents("0.expected")
            assert actual == expected

            # 1 change descriptions
            cur.execute(
                "select ai.set_description('bob', 'this is a BETTER comment about the bob table')"
            )
            cur.execute(
                "select ai.set_column_description('bobby', 'id', 'this is a BETTER comment about the id column')"
            )
            cur.execute(
                """
                select ai.set_function_description
                ( 'life'::regproc
                , 'this is a BETTER comment about the life function'
                )
                """
            )
            con.commit()
            snapshot_descriptions("text_to_sql_1", "1")
            actual = file_contents("1.actual")
            expected = file_contents("1.expected")
            assert actual == expected

            # 2 rename function
            cur.execute("alter function life(int) rename to death")
            con.commit()
            snapshot_descriptions("text_to_sql_1", "2")
            actual = file_contents("2.actual")
            expected = file_contents("2.expected")
            assert actual == expected

            # 3 rename table column
            cur.execute("alter table bob rename column foo to baz")
            con.commit()
            snapshot_descriptions("text_to_sql_1", "3")
            actual = file_contents("3.actual")
            expected = file_contents("3.expected")
            assert actual == expected

            # 4 rename view
            cur.execute("alter view bobby rename to frederick")
            con.commit()
            snapshot_descriptions("text_to_sql_1", "4")
            actual = file_contents("4.actual")
            expected = file_contents("4.expected")
            assert actual == expected

            # 5 drop view
            cur.execute("drop view frederick")
            con.commit()
            snapshot_descriptions("text_to_sql_1", "5")
            actual = file_contents("5.actual")
            expected = file_contents("5.expected")
            assert actual == expected

            # 6 drop table column
            cur.execute("alter table bob drop column baz")
            con.commit()
            snapshot_descriptions("text_to_sql_1", "6")
            actual = file_contents("6.actual")
            expected = file_contents("6.expected")
            assert actual == expected

            # 7 alter function set schema
            cur.execute("create schema maria")
            cur.execute("alter function death set schema maria")
            con.commit()
            snapshot_descriptions("text_to_sql_1", "7")
            actual = file_contents("7.actual")
            expected = file_contents("7.expected")
            assert actual == expected

            # 8 alter table set schema
            cur.execute("alter table bob set schema maria")
            con.commit()
            snapshot_descriptions("text_to_sql_1", "8")
            actual = file_contents("8.actual")
            expected = file_contents("8.expected")
            assert actual == expected

            # 9 test overloaded function names
            cur.execute("""
            create function maria.death(x int, y int) returns int
            as $func$select 42$func$ language sql;
            """)
            cur.execute(
                "select ai.set_function_description('maria.death(int, int)', 'overloaded')"
            )
            con.commit()
            snapshot_descriptions("text_to_sql_1", "9")
            actual = file_contents("9.actual")
            expected = file_contents("9.expected")
            assert actual == expected

            # 10 alter schema rename
            cur.execute("alter schema maria rename to lucinda")
            con.commit()
            snapshot_descriptions("text_to_sql_1", "10")
            actual = file_contents("10.actual")
            expected = file_contents("10.expected")
            assert actual == expected

            # 11 drop function
            cur.execute("drop function lucinda.death(int)")
            con.commit()
            snapshot_descriptions("text_to_sql_1", "11")
            actual = file_contents("11.actual")
            expected = file_contents("11.expected")
            assert actual == expected

            # 12 drop table
            cur.execute("drop table lucinda.bob")
            con.commit()
            snapshot_descriptions("text_to_sql_1", "12")
            actual = file_contents("12.actual")
            expected = file_contents("12.expected")
            assert actual == expected

            # 13 drop schema cascade
            cur.execute("drop schema lucinda cascade")
            con.commit()
            snapshot_descriptions("text_to_sql_1", "13")
            actual = file_contents("13.actual")
            expected = file_contents("13.expected")
            assert actual == expected

            cur.execute("delete from ai.semantic_catalog_obj")


def snapshot_catalog(dbname: str) -> None:
    host_dir().joinpath("snapshot-catalog.actual").unlink(missing_ok=True)
    cmd = " ".join(
        [
            "psql",
            f'''-d "{db_url("postgres", dbname)}"''',
            "-v ON_ERROR_STOP=1",
            "-X",
            "--echo-errors",
            f"-o {docker_dir()}/snapshot-catalog.actual",
            f"-f {docker_dir()}/snapshot-catalog.sql",
        ]
    )
    if where_am_i() != "docker":
        cmd = f"docker exec -w {docker_dir()} pgai-ext {cmd}"
    subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))


def test_text_to_sql() -> None:
    ollama_host = os.environ["OLLAMA_HOST"]
    assert ollama_host is not None

    set_up_test_db("text_to_sql_2")
    with psycopg.connect(
        db_url("test", "text_to_sql_2"), row_factory=namedtuple_row
    ) as con:
        with con.cursor() as cur:
            cur.execute("""select ai.grant_ai_usage('test', true)""")
            cur.execute("""
            create table bob
            ( id int not null primary key
            , foo text not null
            , bar timestamptz not null default now()
            );

            create view bobby as
            select * from bob;

            create function life(x int) returns int
            as $func$select 42$func$ language sql;
            """)

            cur.execute(
                """
            select ai.initialize_semantic_catalog
            ( embedding=>ai.embedding_ollama
              ( 'smollm:135m'
              , 576
              , base_url=>%s
              )
            )
            """,
                (ollama_host,),
            )
            con.commit()

            cur.execute("""
            -- table
            select ai.set_description('bob', 'this is a comment about the bob table');
            select ai.set_column_description('bob', 'id', 'this is a comment about the id column');
            select ai.set_column_description('bob', 'foo', 'this is a comment about the foo column');
            select ai.set_column_description('bob', 'bar', 'this is a comment about the bar column');

            -- view
            select ai.set_description('bobby', 'this is a comment about the bob table');
            select ai.set_column_description('bobby', 'id', 'this is a comment about the id column');
            select ai.set_column_description('bobby', 'foo', 'this is a comment about the foo column');
            select ai.set_column_description('bobby', 'bar', 'this is a comment about the bar column');

            -- function
            select ai.set_function_description('life'::regproc, 'this is a comment about the life function');
            
            -- example query
            select ai.add_sql_example
            ( $sql$select * from bobby where id = life(id)$sql$
            , 'a bogus query against the bobby view using the life function'
            );
            """)
            con.commit()

            # generate obj embeddings
            cur.execute(
                """
            insert into ai.semantic_catalog_obj_1_store(embedding_uuid, objtype, objnames, objargs, chunk_seq, chunk, embedding)
            select
              gen_random_uuid()
            , objtype, objnames, objargs
            , 0
            , description
            , ai.ollama_embed('smollm:135m', description, host=>%s)
            from ai.semantic_catalog_obj
            """,
                (ollama_host,),
            )
            cur.execute("delete from ai._vectorizer_q_1")

            # generate sql embeddings
            cur.execute(
                """
            insert into ai.semantic_catalog_sql_1_store(embedding_uuid, id, chunk_seq, chunk, embedding)
            select
              gen_random_uuid()
            , id
            , 0
            , description
            , ai.ollama_embed('smollm:135m', description, host=>%s)
            from ai.semantic_catalog_sql
            """,
                (ollama_host,),
            )
            cur.execute("delete from ai._vectorizer_q_2")

            cur.execute(
                """select * from ai.find_relevant_obj('i need a function about life', objtypes=>array['function'])"""
            )
            for row in cur.fetchall():
                assert row.objtype == "function"
                assert row.objnames == ["public", "life"]
                assert row.objargs == ["integer"]
                assert row.description == "this is a comment about the life function"
                break

            cur.execute(
                """select * from ai.find_relevant_obj('i need a function about life', objtypes=>array['table column'])"""
            )
            for row in cur.fetchall():
                assert row.objtype == "table column"

            cur.execute(
                """select * from ai.find_relevant_obj('i need a function about life', max_dist=>0.4)"""
            )
            for row in cur.fetchall():
                assert row.dist <= 0.4

            cur.execute(
                """select * from ai.find_relevant_sql('i need a query to tell me about bobby''s life')"""
            )
            for row in cur.fetchall():
                assert row.id == 1
                assert row.sql == "select * from bobby where id = life(id)"
                assert (
                    row.description
                    == "a bogus query against the bobby view using the life function"
                )

    snapshot_catalog("text_to_sql_2")
    actual = file_contents("snapshot-catalog.actual")
    expected = file_contents("snapshot-catalog.expected")
    assert actual == expected
