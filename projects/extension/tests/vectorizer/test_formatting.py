import os

import psycopg
import pytest

# skip tests in this module if disabled
enable_vectorizer_tests = os.getenv("ENABLE_VECTORIZER_TESTS")
if enable_vectorizer_tests == "0":
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
                "config_type": "formatting",
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
                "config_type": "formatting",
                "template": "size: $size shape: $shape $chunk",
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


def test_validate_formatting():
    ok = [
        """
        select ai._validate_formatting
        ( ai.formatting_python_template()
        , 'public', 'thing'
        )
        """,
        """
        select ai._validate_formatting
        ( ai.formatting_python_template('color: $color weight: $weight $chunk')
        , 'public', 'thing'
        )
        """,
    ]
    bad = [
        (
            """
            select ai._validate_formatting
            ( ai.scheduling_none()
            , 'public', 'thing'
            )
            """,
            "invalid config_type for formatting config",
        ),
        (
            """
            select ai._validate_formatting
            ( '{"implementation": "jinja2", "config_type": "formatting"}'::jsonb
            , 'public', 'thing'
            )
            """,
            "unrecognized formatting implementation",
        ),
        (
            """
            select ai._validate_formatting
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
            select ai._validate_formatting
            ( ai.formatting_python_template
              ( 'color: $color weight: $weight height: $height $chunk'
              )
            , 'public', 'thing2' -- has a column named "chunk"
            )
            """,
            'formatting_python_template may not be used when source table has a column named "chunk"',
        ),
        (
            """
            select ai._validate_formatting
            ( ai.scheduling_none()
            , 'public', 'thing2' -- has a column named "chunk"
            )
            """,
            "invalid config_type for formatting config",
        ),
    ]
    with psycopg.connect(db_url("test"), autocommit=True) as con:
        with con.cursor() as cur:
            cur.execute("drop table if exists public.thing;")
            cur.execute("create table public.thing (id int, color text, weight float)")
            cur.execute("drop table if exists public.thing2;")
            cur.execute(
                "create table public.thing2 (id int, color text, weight float, chunk text)"
            )
            for query in ok:
                cur.execute(query)
            for query, err in bad:
                try:
                    cur.execute(query)
                except psycopg.ProgrammingError as ex:
                    msg = str(ex.args[0])
                    assert len(msg) >= len(err) and msg[: len(err)] == err
                else:
                    pytest.fail(f"expected exception: {err}")
