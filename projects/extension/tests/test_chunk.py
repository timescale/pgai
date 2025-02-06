import psycopg


def test_chunk_test():
    with psycopg.connect("postgres://test@127.0.0.1:5432/test") as con:
        actuals = {
            0: "if two",
            1: "witches",
            2: "watch two",
            3: "watches,",
            4: "which",
            5: "witch",
            6: "watches",
            7: "which",
            8: "watch?",
        }
        with con.cursor() as cur:
            cur.execute("""
                select *
                from ai.chunk_text
                ($$if two witches watch two watches, which witch watches which watch?$$
                , separator=>' '
                , chunk_size=>10
                , chunk_overlap=>0
                )
            """)
            for row in cur.fetchall():
                k = row[0]
                v = row[1]
                assert k in actuals
                assert v == actuals[k]


def test_chunk_recursively():
    with psycopg.connect("postgres://test@127.0.0.1:5432/test") as con:
        actuals = {
            0: "if",
            1: " two",
            2: " witches",
            3: " watch",
            4: " two",
            5: " watches,",
            6: " which",
            7: " witch",
            8: " watches",
            9: " which",
            10: " watch",
            11: "?",
        }
        with con.cursor() as cur:
            cur.execute("""
                select *
                from ai.chunk_text_recursively
                ($$if two witches watch two watches, which witch watches which watch?$$
                , separators=>array[' ', '.', '?']
                , chunk_size=>2
                , chunk_overlap=>0
                )
            """)
            rows = [row for row in cur.fetchall()]
            for row in rows:
                k = row[0]
                v = row[1]
                assert k in actuals
                assert v == actuals[k]
