import json

import httpx
import backoff


def execute_async_ext_vectorizer(plpy, vectorizer_id: int) -> None:
    plan = plpy.prepare(
        """
        select pg_catalog.to_jsonb(v) as vectorizer
        from ai.vectorizer v
        where v.id = $1
    """,
        ["int"],
    )
    result = plan.execute([vectorizer_id], 1)
    if not result:
        plpy.error(f"vectorizer {vectorizer_id} not found")
    vectorizer = json.loads(result[0]["vectorizer"])

    def on_backoff(detail):
        plpy.warning(
            f"post_vectorizer_execution: {vectorizer_id} retry number: {detail['tries']} elapsed: {detail['elapsed']} wait: {detail['wait']}..."
        )

    @backoff.on_exception(
        backoff.expo, httpx.HTTPError, max_tries=10, max_time=120, on_backoff=on_backoff
    )
    def post_vectorizer_execution(v: dict) -> httpx.Response:
        return httpx.post("http://localhost:8000/", json=v)

    r = post_vectorizer_execution(vectorizer)
    if r.status_code != httpx.codes.OK:
        plpy.error(f"failed to signal vectorizer execution: {r.status_code}")
