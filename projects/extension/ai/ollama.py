from ollama import Client


def get_ollama_host(plpy) -> str:
    r = plpy.execute(
        "select pg_catalog.current_setting('ai.ollama_host', true) as ollama_host"
    )
    if len(r) == 0:
        host = "http://localhost:11434"
        plpy.warning(f"defaulting Ollama host to: {host}")
        return host
    return r[0]["ollama_host"]


def make_client(plpy, host: str | None = None) -> Client:
    if host is None:
        host = get_ollama_host(plpy)
    return Client(host)
