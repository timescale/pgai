import json
from urllib.parse import urljoin

import backoff
import httpx
from backoff._typing import Details

from .utils import get_guc_value

GUC_VECTORIZER_URL = "ai.external_functions_executor_url"
DEFAULT_VECTORIZER_URL = "http://localhost:8000"

GUC_VECTORIZER_PATH = "ai.external_functions_executor_events_path"
DEFAULT_VECTORIZER_PATH = "/api/v1/events"


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

    embedding_api_key = (
        vectorizer.get("config", {}).get("embedding", {}).get("api_key_name", None)
    )
    vectorizer["secrets"] = [embedding_api_key] if embedding_api_key else []

    the_url = urljoin(
        get_guc_value(plpy, GUC_VECTORIZER_URL, DEFAULT_VECTORIZER_URL),
        get_guc_value(plpy, GUC_VECTORIZER_PATH, DEFAULT_VECTORIZER_PATH),
    )
    plpy.debug(f"posting execution request to {the_url}")

    def on_backoff(detail: Details):
        wait = detail.get("wait", 0)
        plpy.warning(
            f"{vectorizer_id} retry: {detail['tries']} elapsed: {detail['elapsed']} wait: {wait}..."
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
