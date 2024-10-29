import os

import psycopg
import pytest

# skip tests in this module if disabled
enable_vectorizer_tests = os.getenv("ENABLE_VECTORIZER_TESTS")
if enable_vectorizer_tests == "0":
    pytest.skip(allow_module_level=True)


def db_url(user: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/test"


def test_indexing_none():
    tests = [
        (
            "select ai.indexing_none()",
            {
                "implementation": "none",
                "config_type": "indexing",
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


def test_indexing_diskann():
    tests = [
        (
            "select ai.indexing_diskann()",
            {
                "implementation": "diskann",
                "config_type": "indexing",
                "min_rows": 100_000,
                "create_when_queue_empty": True,
            },
        ),
        (
            "select ai.indexing_diskann(min_rows=>500)",
            {
                "implementation": "diskann",
                "config_type": "indexing",
                "min_rows": 500,
                "create_when_queue_empty": True,
            },
        ),
        (
            "select ai.indexing_diskann(storage_layout=>'plain')",
            {
                "implementation": "diskann",
                "config_type": "indexing",
                "min_rows": 100_000,
                "storage_layout": "plain",
                "create_when_queue_empty": True,
            },
        ),
        (
            "select ai.indexing_diskann(storage_layout=>'plain', create_when_queue_empty=>false)",
            {
                "implementation": "diskann",
                "config_type": "indexing",
                "min_rows": 100_000,
                "storage_layout": "plain",
                "create_when_queue_empty": False,
            },
        ),
        (
            """
            select ai.indexing_diskann
            ( storage_layout=>'memory_optimized'
            , num_neighbors=>50
            , search_list_size=>150
            , max_alpha=>1.2
            , num_dimensions=>768
            , num_bits_per_dimension=>2
            )
            """,
            {
                "implementation": "diskann",
                "config_type": "indexing",
                "min_rows": 100_000,
                "storage_layout": "memory_optimized",
                "num_neighbors": 50,
                "search_list_size": 150,
                "max_alpha": 1.2,
                "num_dimensions": 768,
                "num_bits_per_dimension": 2,
                "create_when_queue_empty": True,
            },
        ),
        (
            """
            select ai.indexing_diskann
            ( storage_layout=>'memory_optimized'
            , num_neighbors=>50
            , search_list_size=>150
            , max_alpha=>1.2
            , num_dimensions=>768
            , num_bits_per_dimension=>2
            , create_when_queue_empty=>false
            )
            """,
            {
                "implementation": "diskann",
                "config_type": "indexing",
                "min_rows": 100_000,
                "storage_layout": "memory_optimized",
                "num_neighbors": 50,
                "search_list_size": 150,
                "max_alpha": 1.2,
                "num_dimensions": 768,
                "num_bits_per_dimension": 2,
                "create_when_queue_empty": False,
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


def test_indexing_hnsw():
    tests = [
        (
            "select ai.indexing_hnsw()",
            {
                "implementation": "hnsw",
                "config_type": "indexing",
                "min_rows": 100_000,
                "opclass": "vector_cosine_ops",
                "create_when_queue_empty": True,
            },
        ),
        (
            "select ai.indexing_hnsw(min_rows=>500)",
            {
                "implementation": "hnsw",
                "config_type": "indexing",
                "min_rows": 500,
                "opclass": "vector_cosine_ops",
                "create_when_queue_empty": True,
            },
        ),
        (
            "select ai.indexing_hnsw(opclass=>'vector_l1_ops')",
            {
                "implementation": "hnsw",
                "config_type": "indexing",
                "min_rows": 100_000,
                "opclass": "vector_l1_ops",
                "create_when_queue_empty": True,
            },
        ),
        (
            "select ai.indexing_hnsw(m=>10, ef_construction=>100)",
            {
                "implementation": "hnsw",
                "config_type": "indexing",
                "min_rows": 100_000,
                "m": 10,
                "ef_construction": 100,
                "opclass": "vector_cosine_ops",
                "create_when_queue_empty": True,
            },
        ),
        (
            "select ai.indexing_hnsw(m=>10, ef_construction=>100, create_when_queue_empty=>false)",
            {
                "implementation": "hnsw",
                "config_type": "indexing",
                "min_rows": 100_000,
                "m": 10,
                "ef_construction": 100,
                "opclass": "vector_cosine_ops",
                "create_when_queue_empty": False,
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


def test_validate_indexing():
    ok = [
        "select ai._validate_indexing(ai.indexing_none())",
        "select ai._validate_indexing(ai.indexing_hnsw())",
        "select ai._validate_indexing(ai.indexing_hnsw(opclass=>'vector_ip_ops'))",
        "select ai._validate_indexing(ai.indexing_hnsw(opclass=>'vector_cosine_ops'))",
        "select ai._validate_indexing(ai.indexing_hnsw(opclass=>'vector_l1_ops'))",
        "select ai._validate_indexing(ai.indexing_hnsw(opclass=>null))",
        "select ai._validate_indexing(ai.indexing_hnsw(create_when_queue_empty=>false))",
        "select ai._validate_indexing(ai.indexing_diskann())",
        "select ai._validate_indexing(ai.indexing_diskann(storage_layout=>'plain'))",
        "select ai._validate_indexing(ai.indexing_diskann(storage_layout=>'memory_optimized'))",
        "select ai._validate_indexing(ai.indexing_diskann(storage_layout=>null))",
        "select ai._validate_indexing(ai.indexing_diskann(create_when_queue_empty=>false))",
    ]
    bad = [
        (
            "select ai._validate_indexing(ai.indexing_hnsw(opclass=>'peter'))",
            "invalid opclass",
        ),
        (
            "select ai._validate_indexing(ai.indexing_diskann(storage_layout=>'super_advanced'))",
            "invalid storage",
        ),
        (
            "select ai._validate_indexing(ai.scheduling_none())",
            "invalid config_type for indexing config",
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
