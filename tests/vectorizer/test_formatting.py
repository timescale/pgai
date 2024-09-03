import os

import psycopg
import pytest

# skip tests in this module if disabled
enable_vectorizer_tests = os.getenv("ENABLE_VECTORIZER_TESTS")
if not enable_vectorizer_tests or enable_vectorizer_tests == "0":
    pytest.skip(allow_module_level=True)


def db_url(user: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/test"


def test_formatting_python_template():
    tests = [
        (
            """
            select ai.formatting_python_template()
            """,
            {
                "implementation": "python_template",
                "template": "$chunk",
            },
        ),
        (
            """
            select ai.formatting_python_template
            ( 'size: $size shape: $shape $chunk'
            )
            """,
            {
                "implementation": "python_template",
                "template": "size: $size shape: $shape $chunk",
            },
        ),
        (
            """
            select ai.formatting_python_template
            ( 'size: $size shape: $shape $chunk'
            , columns=>array['size', 'shape']
            )
            """,
            {
                "implementation": "python_template",
                "columns": ["size", "shape"],
                "template": "size: $size shape: $shape $chunk",
            },
        ),
        (
            """
            select ai.formatting_python_template
            ( 'color: $color weight: $weight category: $category $chunk'
            , columns=>array['color', 'weight', 'category']
            )
            """,
            {
                "implementation": "python_template",
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


def test_validate_formatting_python_template():
    ok = [
        (
            """
            select ai._validate_formatting_python_template
            ( ai.formatting_python_template()
            , 'public', 'thing'
            )
            """,
            {
                "implementation": "python_template",
                "columns": ["id", "color", "weight"],
                "template": "$chunk",
            },
        ),
        (
            """
            select ai._validate_formatting_python_template
            ( ai.formatting_python_template('color: $color weight: $weight $chunk')
            , 'public', 'thing'
            )
            """,
            {
                "implementation": "python_template",
                "columns": ["id", "color", "weight"],
                "template": "color: $color weight: $weight $chunk",
            },
        ),
        (
            """
            select ai._validate_formatting_python_template
            ( ai.formatting_python_template
              ( 'color: $color weight: $weight $chunk'
              , columns=>array['color', 'weight']
              )
            , 'public', 'thing'
            )
            """,
            {
                "implementation": "python_template",
                "columns": ["color", "weight"],
                "template": "color: $color weight: $weight $chunk",
            },
        ),
    ]
    bad = [
        (
            """
            select ai._validate_formatting_python_template
            ( ai.formatting_python_template
              ( 'color: $color weight: $weight height: $height $chunk'
              , columns=>array['color', 'weight', 'height']
              )
            , 'public', 'thing'
            )
            """,
            "columns in config do not exist in the table: height",
        ),
        (
            """
            select ai._validate_formatting_python_template
            ( ai.formatting_python_template
              ( 'color: $color weight: $weight height: $height' -- no $chunk
              )
            , 'public', 'thing'
            )
            """,
            "template must contain $chunk placeholder",
        ),
        (
            """
            select ai._validate_formatting_python_template
            ( ai.formatting_python_template
              ( 'color: $color weight: $weight height: $height $chunk'
              )
            , 'public', 'thing2' -- has a column named "chunk"
            )
            """,
            'formatting_python_template may not be used when source table has a column named "chunk"',
        ),
    ]
    with psycopg.connect(db_url("test"), autocommit=True) as con:
        with con.cursor() as cur:
            cur.execute("drop table if exists public.thing;")
            cur.execute("create table public.thing (id int, color text, weight float)")
            cur.execute("drop table if exists public.thing2;")
            cur.execute("create table public.thing2 (id int, color text, weight float, chunk text)")
            for query, expected in ok:
                cur.execute(query)
                actual = cur.fetchone()[0]
                assert actual.keys() == expected.keys()
                for k, v in actual.items():
                    assert k in expected and v == expected[k]
            for query, err in bad:
                try:
                    cur.execute(query)
                except psycopg.ProgrammingError as ex:
                    msg = str(ex.args[0])
                    assert len(msg) >= len(err) and msg[:len(err)] == err
                else:
                    pytest.fail(f"expected exception: {err}")
