import os

import psycopg
import pytest

# skip tests in this module if disabled
enable_vectorizer_tests = os.getenv("ENABLE_VECTORIZER_TESTS")
if not enable_vectorizer_tests or enable_vectorizer_tests == "0":
    pytest.skip(allow_module_level=True)


def db_url(user: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/test"


def test_scheduling_none():
    tests = [
        (
            "select ai.scheduling_none()",
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


def test_scheduling_pg_cron():
    tests = [
        (
            "select ai.scheduling_pg_cron()",
            {
                "implementation": "pg_cron",
                "schedule": "*/10 * * * *",
            },
        ),
        (
            "select ai.scheduling_pg_cron('*/5 * * * *')",
            {
                "implementation": "pg_cron",
                "schedule": "*/5 * * * *",
            },
        ),
        (
            "select ai.scheduling_pg_cron('0 * * * *')",
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


def test_scheduling_timescaledb():
    tests = [
        (
            "select ai.scheduling_timescaledb()",
            {
                "implementation": "timescaledb",
                "schedule_interval": "00:10:00",
            },
        ),
        (
            "select ai.scheduling_timescaledb(interval '5m')",
            {
                "implementation": "timescaledb",
                "schedule_interval": "00:05:00",
            },
        ),
        (
            "select ai.scheduling_timescaledb(interval '1h', timezone=>'America/Chicago')",
            {
                "implementation": "timescaledb",
                "schedule_interval": "01:00:00",
                "timezone": "America/Chicago",
            },
        ),
        (
            "select ai.scheduling_timescaledb(interval '10m', fixed_schedule=>true, timezone=>'America/Chicago')",
            {
                "implementation": "timescaledb",
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
