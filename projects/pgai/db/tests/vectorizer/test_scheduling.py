import os

import psycopg
import pytest

# skip tests in this module if disabled
enable_vectorizer_tests = os.getenv("ENABLE_VECTORIZER_TESTS")
if enable_vectorizer_tests == "0":
    pytest.skip(allow_module_level=True)


def db_url(user: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/test"


def test_scheduling_none():
    tests = [
        (
            "select ai.scheduling_none()",
            {
                "implementation": "none",
                "config_type": "scheduling",
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


def test_scheduling_timescaledb():
    tests = [
        (
            "select ai.scheduling_timescaledb()",
            {
                "implementation": "timescaledb",
                "config_type": "scheduling",
                "schedule_interval": "00:05:00",
            },
        ),
        (
            "select ai.scheduling_timescaledb(interval '10m')",
            {
                "implementation": "timescaledb",
                "config_type": "scheduling",
                "schedule_interval": "00:10:00",
            },
        ),
        (
            "select ai.scheduling_timescaledb(interval '1h', timezone=>'America/Chicago')",
            {
                "implementation": "timescaledb",
                "config_type": "scheduling",
                "schedule_interval": "01:00:00",
                "timezone": "America/Chicago",
            },
        ),
        (
            "select ai.scheduling_timescaledb(interval '10m', fixed_schedule=>true, timezone=>'America/Chicago')",
            {
                "implementation": "timescaledb",
                "config_type": "scheduling",
                "schedule_interval": "00:10:00",
                "timezone": "America/Chicago",
                "fixed_schedule": True,
            },
        ),
        (
            """
            select ai.scheduling_timescaledb
            ( interval '15m'
            , initial_start=>'2025-01-06 America/Chicago'::timestamptz
            , fixed_schedule=>false
            , timezone=>'America/Chicago'
            )
            """,
            {
                "implementation": "timescaledb",
                "config_type": "scheduling",
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


@pytest.mark.parametrize(
    "setting,expected",
    [
        (
            None,  # default case - no setting
            {
                "implementation": "none",
                "config_type": "scheduling",
            },
        ),
        (
            "scheduling_timescaledb",
            {
                "implementation": "timescaledb",
                "config_type": "scheduling",
                "schedule_interval": "00:05:00",
            },
        ),
        (
            "scheduling_none",
            {
                "implementation": "none",
                "config_type": "scheduling",
            },
        ),
        (
            "invalid_value",  # should default to none
            {
                "implementation": "none",
                "config_type": "scheduling",
            },
        ),
    ],
)
def test_scheduling_default(setting, expected):
    with psycopg.connect(db_url("test")) as con:
        with con.cursor() as cur:
            if setting is not None:
                cur.execute(f"set ai.scheduling_default = '{setting}'")
            cur.execute("select ai._resolve_scheduling_default()")
            actual = cur.fetchone()[0]
            assert actual.keys() == expected.keys()
            for k, v in actual.items():
                assert k in expected and v == expected[k]


def test_validate_scheduling():
    ok = [
        "select ai._validate_scheduling(ai.scheduling_none())",
        "select ai._validate_scheduling(ai.scheduling_timescaledb())",
    ]
    bad = [
        (
            "select ai._validate_scheduling(ai.indexing_hnsw(opclass=>'peter'))",
            "invalid config_type for scheduling config",
        ),
        (
            """select ai._validate_scheduling('{"config_type": "scheduling"}'::jsonb)""",
            "scheduling implementation not specified",
        ),
        (
            """
            select ai._validate_scheduling
            ( '{"config_type": "scheduling", "implementation": "grandfather clock"}'::jsonb
            )
            """,
            'unrecognized scheduling implementation: "grandfather clock"',
        ),
    ]
    with psycopg.connect(db_url("test"), autocommit=True) as con:
        with con.cursor() as cur:
            for query in ok:
                cur.execute(query)
                assert True
            for query, err in bad:
                try:
                    cur.execute(query)
                except psycopg.ProgrammingError as ex:
                    msg = str(ex.args[0])
                    assert len(msg) >= len(err) and msg[: len(err)] == err
                else:
                    pytest.fail(f"expected exception: {err}")
