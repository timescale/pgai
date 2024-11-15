import json
import asyncio
import openai
from typing import Optional, Any, Dict, Callable, Awaitable
from .secrets import reveal_secret


def get_openai_api_key(plpy, api_key_name: Optional[str] = None) -> str:
    if api_key_name is None:
        api_key_name = "OPENAI_API_KEY"
    key = reveal_secret(plpy, api_key_name)
    if key is None:
        plpy.error(f"missing {api_key_name} secret")
        # This line should never be reached, but it's here to make the type checker happy.
        return ""
    return key


def get_openai_base_url(plpy) -> Optional[str]:
    r = plpy.execute(
        "SELECT pg_catalog.current_setting('ai.openai_base_url', true) AS base_url"
    )
    if len(r) == 0:
        return None
    return r[0]["base_url"]


def make_async_client(
        plpy,
        api_key: Optional[str] = None,
        api_key_name: Optional[str] = None,
        organization: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        default_headers: Optional[Dict[str, str]] = None,
        default_query: Optional[Dict[str, Any]] = None,
        http_client: Optional[Any] = None,
        _strict_response_validation: Optional[bool] = None
) -> openai.AsyncOpenAI:
    if api_key is None:
        api_key = get_openai_api_key(plpy, api_key_name)
    if base_url is None:
        base_url = get_openai_base_url(plpy)

    client_kwargs = prepare_kwargs({
        "api_key": api_key,
        "organization": organization,
        "base_url": base_url,
        "timeout": timeout,
        "max_retries": max_retries,
        "default_headers": default_headers,
        "default_query": default_query,
        "http_client": http_client,
        "_strict_response_validation": _strict_response_validation
    })

    return openai.AsyncOpenAI(**client_kwargs)

def get_or_create_client(plpy, GD: Dict[str, Any], api_key: str = None, api_key_name: str = None, base_url: str = None, **client_kwargs) -> Any:
    new_config = prepare_kwargs({'api_key': api_key, 'api_key_name': api_key_name, 'base_url': base_url, **client_kwargs})
    old_config = GD.get('openai_client', {}).get('config', {})
    merged_config = {**old_config, **new_config}

    client_needs_update = (
            'openai_client' not in GD or
            'client' not in GD.get('openai_client', {}) or
            client_config_changed(old_config, merged_config)
    )

    if client_needs_update:
        client = make_async_client(plpy, **merged_config)
        GD['openai_client'] = {'client': client, 'config': merged_config}
    else:
        client = GD['openai_client']['client']

    return client


def process_json_input(input_value):
    return json.loads(input_value) if input_value is not None else None


def is_query_cancelled(plpy):
    try:
        plpy.execute("SELECT 1")
        return False
    except plpy.SPIError:
        return True


def execute_with_cancellation(plpy, client: openai.AsyncOpenAI, async_func: Callable[[openai.AsyncOpenAI, Dict[str, Any]], Awaitable[Dict[str, Any]]], **kwargs) -> Dict[str, Any]:
    async def main():
        task = asyncio.create_task(async_func(client, kwargs))
        while not task.done():
            if is_query_cancelled(plpy):
                task.cancel()
                raise plpy.SPIError("Query cancelled by user")
            await asyncio.sleep(0.1)  # 100ms
        return await task

    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(main())
    return result


def prepare_kwargs(params: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in params.items() if v is not None}


def client_config_changed(old_config: Dict[str, Any], new_config: Dict[str, Any]) -> bool:
    return any(old_config.get(k) != new_config.get(k) for k in new_config)