import json

import httpx
import backoff
from backoff._typing import Details

GUC_VECTORIZER_URL = "ai.vectorizer_url"
DEFAULT_VECTORIZER_URL = "http://localhost:8000"


def get_guc_value(plpy, setting: str, default: str) -> str:
    plan = plpy.prepare("select pg_catalog.current_setting($1, true) as val", ["text"])
    result = plan.execute([setting], 1)
    val: str | None = None
    if len(result) != 0:
        val = result[0]["val"]
    if val is None:
        val = default
    return val


def execute_vectorizer(plpy, vectorizer_id: int) -> None:
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

    the_url = get_guc_value(plpy, GUC_VECTORIZER_URL, DEFAULT_VECTORIZER_URL)

    def on_backoff(detail: Details):
        plpy.warning(
            f"{vectorizer_id} retry: {detail['tries']} elapsed: {detail['elapsed']} wait: {detail['wait']}..."
        )

    @backoff.on_exception(
        backoff.expo,
        httpx.HTTPError,
        max_tries=10,
        max_time=120,
        on_backoff=on_backoff,
        raise_on_giveup=True,
    )
    def post() -> httpx.Response:
        return httpx.post(the_url, json=vectorizer)

    r = post()
    if r.status_code != httpx.codes.OK:
        plpy.error(
            f"failed to signal vectorizer execution: {r.status_code}", detail=r.text
        )
