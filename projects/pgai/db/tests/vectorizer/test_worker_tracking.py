import os

import psycopg
import pytest
from psycopg.rows import dict_row

# skip tests in this module if disabled
enable_vectorizer_tests = os.getenv("ENABLE_VECTORIZER_TESTS")
if enable_vectorizer_tests == "0":
    pytest.skip(allow_module_level=True)


def db_url(user: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/test"


def test_worker_tracking_connection():
    with psycopg.connect(db_url("test")) as con:
        with con.cursor(row_factory=dict_row) as cur:
            row = cur.execute(
                "select ai._worker_start('0.1.1', interval '2 second') as worker_id"
            ).fetchone()
            worker_id = row["worker_id"]

            cur.execute("select ai._worker_heartbeat(%s, 1, 0, null)", (worker_id,))
            cur.execute(
                "select id, version, heartbeat_count, error_count, last_error_at, last_error_message, success_count from ai.vectorizer_worker_process where id = %s",
                (worker_id,),
            )
            row = cur.fetchone()
            assert row is not None
            assert row == {
                "id": worker_id,
                "version": "0.1.1",
                "heartbeat_count": 1,
                "error_count": 0,
                "last_error_at": None,
                "last_error_message": None,
                "success_count": 1,
            }
        con.commit()

        with con.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "select ai._worker_heartbeat(%s, 0, 3, 'error 1')", (worker_id,)
            )
            cur.execute(
                "select id, version, heartbeat_count, error_count, last_error_at, last_error_message, last_heartbeat, success_count from ai.vectorizer_worker_process where id = %s",
                (worker_id,),
            )
            row = cur.fetchone()
            assert row is not None
            assert row["last_error_at"] is not None
            last_error_at = row["last_error_at"]
            assert row == {
                "id": worker_id,
                "version": "0.1.1",
                "heartbeat_count": 2,
                "error_count": 3,
                "last_error_at": last_error_at,
                "last_error_message": "error 1",
                "last_heartbeat": last_error_at,
                "success_count": 1,
            }
        con.commit()

        with con.cursor(row_factory=dict_row) as cur:
            cur.execute("select ai._worker_heartbeat(%s,1, 0, null)", (worker_id,))
            cur.execute(
                "select id, version, heartbeat_count, error_count, last_error_at, last_error_message, last_heartbeat, success_count from ai.vectorizer_worker_process where id = %s",
                (worker_id,),
            )
            row = cur.fetchone()
            assert row is not None
            last_heartbeat = row["last_heartbeat"]
            assert last_heartbeat > last_error_at
            assert row == {
                "id": worker_id,
                "version": "0.1.1",
                "heartbeat_count": 3,
                "error_count": 3,
                "last_error_at": last_error_at,
                "last_error_message": "error 1",
                "last_heartbeat": last_heartbeat,
                "success_count": 2,
            }
        con.commit()

        with con.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "select ai._worker_heartbeat(%s, 0, 1, 'error 2')", (worker_id,)
            )
            cur.execute(
                "select id, version, heartbeat_count, error_count, last_error_at, last_error_message, last_heartbeat, success_count from ai.vectorizer_worker_process where id = %s",
                (worker_id,),
            )
            row = cur.fetchone()
            assert row is not None
            assert row["last_error_at"] > last_error_at
            last_error_at = row["last_error_at"]
            assert row == {
                "id": worker_id,
                "version": "0.1.1",
                "heartbeat_count": 4,
                "error_count": 4,
                "last_error_at": last_error_at,
                "last_error_message": "error 2",
                "last_heartbeat": last_error_at,
                "success_count": 2,
            }
        con.commit()


def test_worker_tracking_progress():
    with psycopg.connect(db_url("test")) as con:
        with con.cursor(row_factory=dict_row) as cur:
            cur.execute("drop table if exists blog")
            cur.execute("""
                create table blog
                ( id int not null generated always as identity
                , title text not null
                , published timestamptz
                , body text not null
                , drop_me text
                , primary key (title, published)
                )
            """)

            cur.execute("""
            select ai.create_vectorizer
                ( 'blog'::regclass
                , loading => ai.loading_column('body')
                , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
                , chunking=>ai.chunking_character_text_splitter(128, 10)
                , formatting=>ai.formatting_python_template('title: $title published: $published $chunk')
                ) as vectorizer_id;
            """)
            vectorizer_id = cur.fetchone()["vectorizer_id"]

            row = cur.execute(
                "select ai._worker_start('0.1.1', interval '2 second') as worker_id"
            ).fetchone()
            worker_id = row["worker_id"]

            cur.execute(
                "select ai._worker_progress(%s, %s, 1, null)",
                (worker_id, vectorizer_id),
            )
            cur.execute(
                "select vectorizer_id, last_success_at, last_error_at, last_error_message, last_success_process_id, last_error_process_id, success_count, error_count from ai.vectorizer_worker_progress where vectorizer_id = %s",
                (vectorizer_id,),
            )
            row = cur.fetchone()
            assert row is not None
            assert row["vectorizer_id"] == vectorizer_id
            assert row["last_success_at"] is not None
            assert row["last_error_at"] is None
            assert row["last_error_message"] is None
            assert row["last_success_process_id"] == worker_id
            assert row["last_error_process_id"] is None
            assert row["success_count"] == 1
            assert row["error_count"] == 0

            cur.execute(
                "select ai._worker_progress(%s, %s, 0, 'error 1')",
                (worker_id, vectorizer_id),
            )
            cur.execute(
                "select vectorizer_id, last_success_at, last_error_at, last_error_message, last_success_process_id, last_error_process_id, success_count, error_count from ai.vectorizer_worker_progress where vectorizer_id = %s",
                (vectorizer_id,),
            )
            row = cur.fetchone()
            assert row is not None
            assert row["vectorizer_id"] == vectorizer_id
            assert row["last_success_at"] is not None
            assert row["last_error_at"] is not None
            last_error_at = row["last_error_at"]
            assert row["last_error_message"] == "error 1"
            assert row["last_success_process_id"] == worker_id
            assert row["last_error_process_id"] == worker_id
            assert row["success_count"] == 1
            assert row["error_count"] == 1
        con.commit()

        with con.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "select ai._worker_progress(%s, %s, 1, null)",
                (worker_id, vectorizer_id),
            )
            cur.execute(
                "select vectorizer_id, last_success_at, last_error_at, last_error_message, last_success_process_id, last_error_process_id, success_count, error_count from ai.vectorizer_worker_progress where vectorizer_id = %s",
                (vectorizer_id,),
            )
            row = cur.fetchone()
            assert row is not None
            assert row["vectorizer_id"] == vectorizer_id
            assert row["last_success_at"] > last_error_at
            assert row["last_error_at"] == last_error_at
            assert row["last_error_message"] == "error 1"
            assert row["last_success_process_id"] == worker_id
            assert row["last_error_process_id"] == worker_id
            assert row["success_count"] == 2
            assert row["error_count"] == 1
        con.commit()
