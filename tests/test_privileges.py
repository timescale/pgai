from typing import Optional

import psycopg
import pytest

pytest.skip(allow_module_level=True)  # todo: remove when working


def db_url(user: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/test"


def does_user_exist(cur: psycopg.Cursor, user: str) -> bool:
    cur.execute("""
        select count(*) > 0
        from pg_catalog.pg_roles
        where rolname = %s
    """, (user,))
    return cur.fetchone()[0]


def list_tables() -> list[str]:
    with psycopg.connect(db_url("postgres")) as con:
        with con.cursor() as cur:
            cur.execute("""
                select pg_catalog.format
                ( '%I.%I'
                , n.nspname
                , k.relname
                )
                from pg_catalog.pg_depend d
                inner join pg_catalog.pg_extension e on (d.refobjid operator(pg_catalog.=) e.oid)
                inner join pg_catalog.pg_class k on (d.objid operator(pg_catalog.=) k.oid)
                inner join pg_catalog.pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
                where k.relkind in ('r', 'p') -- tables and sequences
                and n.nspname operator(pg_catalog.=) 'ai'
                order by n.nspname, k.relname
            """)
            return [x[0] for x in cur.fetchall()]


def list_sequences() -> list[str]:
    with psycopg.connect(db_url("postgres")) as con:
        with con.cursor() as cur:
            cur.execute("""
                select pg_catalog.format
                ( '%I.%I'
                , n.nspname
                , k.relname
                )
                from pg_catalog.pg_depend d
                inner join pg_catalog.pg_extension e on (d.refobjid operator(pg_catalog.=) e.oid)
                inner join pg_catalog.pg_class k on (d.objid operator(pg_catalog.=) k.oid)
                inner join pg_catalog.pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
                where k.relkind in ('S') -- tables and sequences
                and n.nspname operator(pg_catalog.=) 'ai'
                order by n.nspname, k.relname
            """)
            return [x[0] for x in cur.fetchall()]


def list_functions() -> list[tuple[int, str]]:
    with psycopg.connect(db_url("postgres")) as con:
        with con.cursor() as cur:
            cur.execute("""
                select
                  k.oid
                , pg_catalog.format
                ( '%I.%I(%s)'
                , n.nspname
                , k.proname
                , pg_get_function_identity_arguments(k.oid)
                )
                from pg_catalog.pg_depend d
                inner join pg_catalog.pg_extension e on (d.refobjid operator(pg_catalog.=) e.oid)
                inner join pg_catalog.pg_proc k on (d.objid operator(pg_catalog.=) k.oid)
                inner join pg_namespace n on (k.pronamespace operator(pg_catalog.=) n.oid)
                where d.refclassid operator(pg_catalog.=) 'pg_catalog.pg_extension'::pg_catalog.regclass
                and d.deptype operator(pg_catalog.=) 'e'
                and e.extname operator(pg_catalog.=) 'ai'
                and k.prokind in ('f', 'p')
            """)
            return [(x[0], x[1]) for x in cur.fetchall()]


def has_schema_privilege(cur: psycopg.Cursor, user: str, schema: str, privilege: str) -> Optional[str]:
    cur.execute("select has_schema_privilege(%s, %s, %s)", (user, schema, privilege))
    return schema if cur.fetchone()[0] else None


def has_table_privilege(cur: psycopg.Cursor, user: str, table: str, privilege: str) -> Optional[str]:
    cur.execute("select has_table_privilege(%s, %s, %s)", (user, table, privilege))
    return table if cur.fetchone()[0] else None


def has_sequence_privilege(cur: psycopg.Cursor, user: str, sequence: str, privilege: str) -> Optional[str]:
    cur.execute("select has_sequence_privilege(%s, %s, %s)", (user, sequence, privilege))
    return sequence if cur.fetchone()[0] else None


def has_function_privilege(cur: psycopg.Cursor, user: str, oid: int, function: str, privilege: str) -> Optional[str]:
    cur.execute("select has_function_privilege(%s, %s, %s)", (user, oid, privilege))
    return function if cur.fetchone()[0] else None


def test_bob():
    with psycopg.connect(db_url("postgres")) as con:
        with con.cursor() as cur:
            if does_user_exist(cur, user="bob"):
                cur.execute("drop user bob")
            cur.execute("create user bob")
            assert has_schema_privilege(cur, "bob", "ai", "usage") is None
            for table in list_tables():
                assert has_table_privilege(cur, "bob", table, "insert") is None
                assert has_table_privilege(cur, "bob", table, "update") is None
                assert has_table_privilege(cur, "bob", table, "delete") is None
            for oid, func in list_functions():
                assert has_function_privilege(cur, "bob", oid, func, "execute") is None
            for seq in list_sequences():
                assert has_sequence_privilege(cur, "bob", seq, "usage") == seq
                assert has_sequence_privilege(cur, "bob", seq, "select") == seq
                assert has_sequence_privilege(cur, "bob", seq, "update") == seq


@pytest.fixture(scope="module", autouse=True)
def fred() -> None:
    with psycopg.connect(db_url("postgres")) as con:
        with con.cursor() as cur:
            if does_user_exist(cur, user="fred"):
                cur.execute("drop user fred")
            cur.execute("create user fred")
            cur.execute("select ai.grant_ai_usage('fred'::regrole)")


def test_fred_schema():
    with psycopg.connect(db_url("fred")) as con:
        with con.cursor() as cur:
            assert has_schema_privilege(cur, "fred", "ai", "usage") == "ai"
            for table in list_tables():
                assert has_table_privilege(cur, "fred", table, "insert") == table
                assert has_table_privilege(cur, "fred", table, "update") == table
                assert has_table_privilege(cur, "fred", table, "delete") == table
            for oid, func in list_functions():
                assert has_function_privilege(cur, "fred", oid, func, "execute") == func
            for seq in list_sequences():
                assert has_sequence_privilege(cur, "fred", seq, "usage") == seq
                assert has_sequence_privilege(cur, "fred", seq, "select") == seq
                assert has_sequence_privilege(cur, "fred", seq, "update") == seq


@pytest.fixture(scope="module", autouse=True)
def alice() -> None:
    with psycopg.connect(db_url("postgres")) as con:
        with con.cursor() as cur:
            if does_user_exist(cur, user="alice"):
                cur.execute("drop user alice")
            cur.execute("create user alice")
            cur.execute("select ai.grant_ai_usage('alice'::regrole, _with_grant=>true)")


@pytest.fixture(scope="module", autouse=True)
def timmy() -> None:
    with psycopg.connect(db_url("postgres")) as con:
        with con.cursor() as cur:
            if does_user_exist(cur, user="timmy"):
                cur.execute("drop user timmy")
            cur.execute("create user timmy")


def test_timmy_via_alice():
    with psycopg.connect(db_url("alice")) as con:
        with con.cursor() as cur:
            cur.execute("select ai.grant_ai_usage('timmy'::regrole)")
    with psycopg.connect(db_url("timmy")) as con:
        with con.cursor() as cur:
            assert has_schema_privilege(cur, "timmy", "ai", "usage") == "ai"
            for table in list_tables():
                assert has_table_privilege(cur, "timmy", table, "insert") == table
                assert has_table_privilege(cur, "timmy", table, "update") == table
                assert has_table_privilege(cur, "timmy", table, "delete") == table
            for oid, func in list_functions():
                assert has_function_privilege(cur, "timmy", oid, func, "execute") == func
            for seq in list_sequences():
                assert has_sequence_privilege(cur, "timmy", seq, "usage") == seq
                assert has_sequence_privilege(cur, "timmy", seq, "select") == seq
                assert has_sequence_privilege(cur, "timmy", seq, "update") == seq
