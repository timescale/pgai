import json
from typing import Optional

import httpx
import backoff


def is_already_pending(plpy, vectorizer_id: int) -> bool:
    plan = plpy.prepare("""
        select now() - r.requested <= interval '1h' as is_already_pending
        from ai.vectorizer_request r
        where r.vectorizer_id = $1
        and r.status = 'pending'
        order by r.requested desc
        limit 1
    """, ["int"])
    results = plan.execute([vectorizer_id], 1)
    return results[0]["is_already_pending"] if results else False


def is_already_running(plpy, vectorizer_id: int) -> bool:
    plan = plpy.prepare("""
        select now() - r.started <= interval '1h' as is_already_running
        from ai.vectorizer_request r
        where r.vectorizer_id = $1
        and r.status = 'running'
        order by r.started desc
        limit 1
    """, ["int"])
    results = plan.execute([vectorizer_id], 1)
    return results[0]["is_already_running"] if results else False


def get_vectorizer(plpy, vectorizer_id: int) -> dict:
    plan = plpy.prepare("""
        select
          id
        , source_schema
        , source_table
        , source_pk
        , target_schema
        , target_table
        , target_column
        , config
        from ai.vectorizer
        where id = $1
    """, ["int"])
    result = plan.execute([vectorizer_id], 1)
    if not result:
        plpy.error(f"vectorizer {vectorizer_id} not found")
    vec = {}
    for k, v in json.loads(result[0]["config"]).items():
        vec[k] = v
    for colname in result.colnames():
        if colname == "config":
            continue
        vec[colname] = result[0][colname]
    return vec


def insert_vectorizer_request(plpy, vectorizer_id: int, args: dict) -> int:
    plan = plpy.prepare("""
        insert into ai.vectorizer_request
        ( vectorizer_id
        , args
        )
        values
        ( $1
        , $2
        )
        returning id
    """, ["int", "jsonb"])
    results = plan.execute([vectorizer_id, json.dumps(args)], 1)
    if results.nrows() != 1:
        plpy.error(f"vectorizer request was not inserted")
    return results[0]["id"]


def request_vectorizer_execution(plpy, exe_id: int) -> None:
    def on_backoff(detail):
        plpy.warning(f"request_vectorizer_execution{detail['args']}: retry number: {detail['tries']} elapsed: {detail['elapsed']} wait: {detail['wait']}...")

    @backoff.on_exception(backoff.expo, httpx.HTTPError, max_tries=10, max_time=120, on_backoff=on_backoff)
    def post_vectorizer_execution(exe_id: int) -> httpx.Response:
        return httpx.post("http://localhost:8000/", json={"id": exe_id})

    r = post_vectorizer_execution(exe_id)
    if r.status_code != httpx.codes.OK:
        plpy.error(f"failed to signal vectorizer execution: {r.status_code}")
    resp = r.json()
    assert resp["id"] == exe_id


def execute_vectorizer(plpy, vectorizer_id: int, force: bool = False) -> Optional[int]:
    if not force and is_already_pending(plpy, vectorizer_id):
        plpy.debug(f"vectorizer {vectorizer_id} already pending.")
        return None
    if not force and is_already_running(plpy, vectorizer_id):
        plpy.debug(f"vectorizer {vectorizer_id} already running.")
        return None
    vec = get_vectorizer(plpy, vectorizer_id)
    exe_id = insert_vectorizer_request(plpy, vectorizer_id, vec)
    request_vectorizer_execution(plpy, exe_id)
    return exe_id

