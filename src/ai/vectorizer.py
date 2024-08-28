import json

import httpx
import backoff

GUC_EXECUTE_VECTORIZER_URL = "ai.execute_vectorizer_url"
DEFAULT_EXECUTE_VECTORIZER_URL = "http://localhost:8000"


def execute_async_ext_vectorizer(plpy, vectorizer_id: int) -> None:
    plan = plpy.prepare(
        """
        select pg_catalog.to_jsonb(v) as vectorizer
        from ai.vectorizer v
        where v.id operator(pg_catalog.=) $1
    """,
        ["int"],
    )
    result = plan.execute([vectorizer_id], 1)
    if not result:
        plpy.error(f"vectorizer {vectorizer_id} not found")
    vectorizer = json.loads(result[0]["vectorizer"])

    # get the url from a postgres setting if it has been set, otherwise use default
    plan = plpy.prepare("select pg_catalog.current_setting($1, true) as execute_vectorizer_url", ["text"])
    result = plan.execute([GUC_EXECUTE_VECTORIZER_URL], 1)
    url: str | None = None
    if len(result) != 0:
        url = result[0]["execute_vectorizer_url"]
    if url is None:
        url = DEFAULT_EXECUTE_VECTORIZER_URL

    def on_backoff(detail):
        plpy.warning(
            f"post_vectorizer_execution: {vectorizer_id} retry number: {detail['tries']} elapsed: {detail['elapsed']} wait: {detail['wait']}..."
        )

    @backoff.on_exception(
        backoff.expo, httpx.HTTPError, max_tries=10, max_time=120, on_backoff=on_backoff
    )
    def post_vectorizer_execution(v: dict) -> httpx.Response:
        return httpx.post(url, json=v)

    r = post_vectorizer_execution(vectorizer)
    if r.status_code != httpx.codes.OK:
        # TODO: only display error text in debug log?
        plpy.error(f"failed to signal vectorizer execution: {r.status_code}\n{r.text}")
