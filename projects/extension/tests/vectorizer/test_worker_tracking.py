import os

import psycopg
import pytest

# skip tests in this module if disabled
enable_vectorizer_tests = os.getenv("ENABLE_VECTORIZER_TESTS")
if enable_vectorizer_tests == "0":
    pytest.skip(allow_module_level=True)


def db_url(user: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/test"


def test_worker_tracking_connection():
    with psycopg.connect(db_url("test")) as con:
        with con.cursor() as cur:
            row = cur.execute("select ai._worker_start('0.1.1', interval '2 second')").fetchone()
            worker_id = row[0]
            
            cur.execute("select ai._worker_heartbeat(%s, 0, null)", (worker_id,))
            cur.execute("select id, version, heartbeat_count, error_count, last_error_at, last_error_message from ai.vectorizer_worker_connection where id = %s", (worker_id,))
            row = cur.fetchone() 
            assert row[0] == worker_id
            assert row[1] == "0.1.1"
            assert row[2] == 1
            assert row[3] == 0
            assert row[4] is None
            assert row[5] is None
        con.commit()
        
        with con.cursor() as cur: 
            cur.execute("select ai._worker_heartbeat(%s, 3, 'error 1')", (worker_id,))
            cur.execute("select id, version, heartbeat_count, error_count, last_error_at, last_error_message, last_heartbeat from ai.vectorizer_worker_connection where id = %s", (worker_id,))
            row = cur.fetchone() 
            assert row[0] == worker_id
            assert row[1] == "0.1.1"
            assert row[2] == 2
            assert row[3] == 3
            assert row[4] is not None
            last_error_at = row[4]
            assert row[5] == "error 1"
            assert row[6] == last_error_at
        con.commit()
        
        with con.cursor() as cur:
            cur.execute("select ai._worker_heartbeat(%s, 0, null)", (worker_id,))
            cur.execute("select id, version, heartbeat_count, error_count, last_error_at, last_error_message, last_heartbeat from ai.vectorizer_worker_connection where id = %s", (worker_id,))
            row = cur.fetchone() 
            assert row[0] == worker_id
            assert row[1] == "0.1.1"
            assert row[2] == 3
            assert row[3] == 3
            assert row[4] == last_error_at
            assert row[5] == "error 1"
            assert row[6] > last_error_at
        con.commit()
        
        with con.cursor() as cur:
            cur.execute("select ai._worker_heartbeat(%s, 1, 'error 2')", (worker_id,))
            cur.execute("select id, version, heartbeat_count, error_count, last_error_at, last_error_message, last_heartbeat from ai.vectorizer_worker_connection where id = %s", (worker_id,))
            row = cur.fetchone() 
            assert row[0] == worker_id
            assert row[1] == "0.1.1"
            assert row[2] == 4
            assert row[3] == 4
            assert row[4] > last_error_at
            assert row[5] == "error 2"
            assert row[6] == row[4]
        con.commit()


def test_worker_tracking_progress():
    with psycopg.connect(db_url("test")) as con:
        with con.cursor() as cur:
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
            , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
            , chunking=>ai.chunking_character_text_splitter('body', 128, 10)
            , formatting=>ai.formatting_python_template('title: $title published: $published $chunk')
            );
            """)
            vectorizer_id = cur.fetchone()[0]
            
            row = cur.execute("select ai._worker_start('0.1.1', interval '2 second')").fetchone()
            worker_id = row[0]
            
            cur.execute("select ai._worker_progress(%s, %s, null)", (worker_id, vectorizer_id))
            cur.execute("select vectorizer_id, last_success_at, last_error_at, last_error_message, last_success_connection_id, last_error_connection_id from ai.vectorizer_worker_progress where vectorizer_id = %s", (vectorizer_id,))
            row = cur.fetchone()
            assert row[0] == vectorizer_id
            assert row[1] is not None
            assert row[2] is None
            assert row[3] is None
            assert row[4] == worker_id
            assert row[5] is None
            
            cur.execute("select ai._worker_progress(%s, %s, 'error 1')", (worker_id, vectorizer_id))
            cur.execute("select vectorizer_id, last_success_at, last_error_at, last_error_message, last_success_connection_id, last_error_connection_id from ai.vectorizer_worker_progress where vectorizer_id = %s", (vectorizer_id,))
            row = cur.fetchone()
            assert row[0] == vectorizer_id
            assert row[1] is not None
            assert row[2] is not None
            last_error_at = row[2]
            assert row[3] == "error 1"
            assert row[4] == worker_id
            assert row[5] == worker_id
        con.commit()
        
        with con.cursor() as cur:
            cur.execute("select ai._worker_progress(%s, %s, null)", (worker_id, vectorizer_id))
            cur.execute("select vectorizer_id, last_success_at, last_error_at, last_error_message, last_success_connection_id, last_error_connection_id from ai.vectorizer_worker_progress where vectorizer_id = %s", (vectorizer_id,))
            row = cur.fetchone()
            assert row[0] == vectorizer_id
            assert row[1] > last_error_at
            assert row[2] == last_error_at
            assert row[3] == "error 1"
            assert row[4] == worker_id
            assert row[5] == worker_id
        con.commit()
