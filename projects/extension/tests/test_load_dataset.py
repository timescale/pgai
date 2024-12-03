import datetime
import os

import psycopg
import pytest


# skip tests in this module if disabled
enable_load_dataset_tests = os.getenv("ENABLE_LOAD_DATASET_TESTS")
if not enable_load_dataset_tests or enable_load_dataset_tests == "0":
    pytest.skip(allow_module_level=True)


@pytest.fixture()
def cur() -> psycopg.Cursor:
    with psycopg.connect("postgres://test@127.0.0.1:5432/test") as con:
        with con.cursor() as cur:
            yield cur


def test_load_dataset(cur):
    # load everything
    cur.execute(
        """
        select ai.load_dataset('rotten_tomatoes')
    """,
    )
    actual = cur.fetchone()[0]
    assert actual == 10662

    cur.execute("select count(*) from public.rotten_tomatoes")
    assert cur.fetchone()[0] == actual

    cur.execute(
        "select column_name, data_type from information_schema.columns where table_name = 'rotten_tomatoes' order by ordinal_position"
    )
    assert cur.fetchall() == [("text", "text"), ("label", "bigint")]

    # test append and explicit split
    cur.execute(
        """
        select ai.load_dataset('rotten_tomatoes', split=>'test', if_table_exists=>'append', batch_size=>2, max_batches=>1)
    """,
    )
    actual = cur.fetchone()[0]
    assert actual == 2

    cur.execute("select count(*) from public.rotten_tomatoes")
    assert cur.fetchone()[0] == 10662 + 2

    # test drop
    cur.execute(
        """
        select ai.load_dataset('rotten_tomatoes', split=>'test', if_table_exists=>'drop', batch_size=>2, max_batches=>1)
    """,
    )
    actual = cur.fetchone()[0]
    assert actual == 2

    cur.execute("select count(*) from public.rotten_tomatoes")
    assert cur.fetchone()[0] == 2

    # test error
    with pytest.raises(Exception):
        cur.execute(
            """
            select ai.load_dataset('rotten_tomatoes', split=>'test', if_table_exists=>'error')
        """,
        )


def test_load_dataset_with_field_types(cur):
    cur.execute(
        """
        select ai.load_dataset('rotten_tomatoes', schema_name=>'public', table_name=>'rotten_tomatoes2', field_types=>'{"label": "int"}'::jsonb, batch_size=>100, max_batches=>1)
    """,
    )
    actual = cur.fetchone()[0]
    assert actual == 100

    cur.execute("select count(*) from public.rotten_tomatoes2")
    assert cur.fetchone()[0] == actual

    cur.execute(
        "select column_name, data_type from information_schema.columns where table_name = 'rotten_tomatoes2' order by ordinal_position"
    )
    assert cur.fetchall() == [("text", "text"), ("label", "integer")]


def test_load_dataset_with_field_with_max_batches_and_timestamp(cur):
    cur.execute(
        """
        select ai.load_dataset('Weijie1996/load_timeseries', batch_size=>2, max_batches=>1)
    """,
    )
    actual = cur.fetchone()[0]
    assert actual == 2

    cur.execute("select count(*) from public.load_timeseries")
    assert cur.fetchone()[0] == actual

    cur.execute(
        "select column_name, data_type from information_schema.columns where table_name = 'load_timeseries' order by ordinal_position"
    )
    assert cur.fetchall() == [
        ("id", "text"),
        ("datetime", "timestamp with time zone"),
        ("target", "double precision"),
        ("category", "text"),
    ]

    cur.execute("select datetime from public.load_timeseries limit 1")
    assert cur.fetchone()[0] == datetime.datetime(
        2015, 5, 21, 15, 45, tzinfo=datetime.timezone.utc
    )


def test_load_dataset_other_datasets(cur):
    # test nyc taxi fare cleaned - timestamp mislabeled as text, force timestamp
    cur.execute("""
                select ai.load_dataset('Chendi/NYC_TAXI_FARE_CLEANED', batch_size=>2, max_batches=>1, field_types=>'{"pickup_datetime": "timestamp with time zone"}'::jsonb)
                """)
    actual = cur.fetchone()[0]
    assert actual == 2

    cur.execute(
        "select column_name, data_type from information_schema.columns where table_name = 'nyc_taxi_fare_cleaned' order by ordinal_position"
    )
    assert cur.fetchall() == [
        ("fare_amount", "double precision"),
        ("pickup_datetime", "timestamp with time zone"),
        ("pickup_longitude", "double precision"),
        ("pickup_latitude", "double precision"),
        ("dropoff_longitude", "double precision"),
        ("dropoff_latitude", "double precision"),
        ("passenger_count", "bigint"),
    ]

    cur.execute("select pickup_datetime from public.nyc_taxi_fare_cleaned limit 1")
    assert cur.fetchone()[0] == datetime.datetime(
        2009, 6, 15, 17, 26, 21, tzinfo=datetime.timezone.utc
    )

    # dataset with sequence column -- become a jsonb column
    cur.execute("""
                select ai.load_dataset('tppllm/nyc-taxi-description', batch_size=>2, max_batches=>1)
                """)
    actual = cur.fetchone()[0]
    assert actual == 2

    cur.execute(
        "select column_name, data_type from information_schema.columns where table_name = 'nyc_taxi_description' order by ordinal_position"
    )
    assert cur.fetchall() == [
        ("dim_process", "bigint"),
        ("seq_idx", "bigint"),
        ("seq_len", "bigint"),
        ("time_since_start", "jsonb"),
        ("time_since_last_event", "jsonb"),
        ("type_event", "jsonb"),
        ("type_text", "jsonb"),
        ("description", "text"),
    ]
