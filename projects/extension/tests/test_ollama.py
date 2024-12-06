import os
import time
import requests
import psycopg
import pytest


# skip tests in this module if disabled
enable_ollama_tests = os.getenv("OLLAMA_HOST")
if not enable_ollama_tests or enable_ollama_tests == "0":
    pytest.skip(allow_module_level=True)


def wait_for_model_download(host: str, model: str, timeout: int = 300) -> None:
    """
    Wait for a model to be downloaded, with timeout.
    Args:
        host: Ollama host URL
        model: Name of the model to wait for
        timeout: Maximum time to wait in seconds
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Check if model exists in list of models
            response = requests.get(f"{host}/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                if any(m["name"] == model for m in models):
                    return
            # If not found, trigger download
            response = requests.post(
                f"{host}/api/pull",
                json={"name": model},
            )
            if response.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(5)
    raise TimeoutError(f"Timeout waiting for model {model} to be ready")


@pytest.fixture(scope="session", autouse=True)
def ensure_models(ollama_host):
    """
    Ensure required models are downloaded before running tests.
    This fixture runs automatically at the start of the test session.
    """
    required_models = ["llama3.2:1b", "smollm:135m"]
    for model in required_models:
        wait_for_model_download(ollama_host, model)


@pytest.fixture(scope="session")
def ollama_host() -> str:
    ollama_host = os.environ["OLLAMA_HOST"]
    return ollama_host


@pytest.fixture()
def cur() -> psycopg.Cursor:
    with psycopg.connect("postgres://test@127.0.0.1:5432/test") as con:
        with con.cursor() as cur:
            yield cur


@pytest.fixture()
def cur_with_ollama_host(ollama_host, cur) -> psycopg.Cursor:
    with cur:
        cur.execute(
            "select set_config('ai.ollama_host', %s, false) is not null",
            (ollama_host,),
        )
        yield cur


def test_ollama_list_models_no_host(cur_with_ollama_host):
    cur_with_ollama_host.execute("select count(*) > 0 from ai.ollama_list_models()")
    actual = cur_with_ollama_host.fetchone()[0]
    assert actual is True


def test_ollama_list_models(cur, ollama_host):
    cur.execute(
        "select count(*) > 0 from ai.ollama_list_models(host=>%s)", (ollama_host,)
    )
    actual = cur.fetchone()[0]
    assert actual is True


def test_ollama_embed(cur, ollama_host):
    cur.execute(
        """
        select vector_dims
        (
            ai.ollama_embed
            ( 'llama3.2:1b'
            , 'the purple elephant sits on a red mushroom'
            , host=>%s
            )
        )
    """,
        (ollama_host,),
    )
    actual = cur.fetchone()[0]
    assert actual == 2048


def test_ollama_embed_no_host(cur_with_ollama_host):
    cur_with_ollama_host.execute("""
        select vector_dims
        (
            ai.ollama_embed
            ( 'llama3.2:1b'
            , 'the purple elephant sits on a red mushroom'
            )
        )
    """)
    actual = cur_with_ollama_host.fetchone()[0]
    assert actual == 2048


def test_ollama_embed_via_openai(cur, ollama_host):
    cur.execute(
        """
        select vector_dims
        (
            ai.openai_embed
            ( 'llama3.2:1b'
            , 'the purple elephant sits on a red mushroom'
            , api_key=>'this is a garbage api key'
            , base_url=>concat(%s::text, '/v1/')
            )
        )
    """,
        (ollama_host,),
    )
    actual = cur.fetchone()[0]
    assert actual == 2048


def test_ollama_generate(cur, ollama_host):
    cur.execute(
        """
        select ai.ollama_generate
        ( 'llama3.2:1b'
        , 'what is the typical weather like in Alabama in June'
        , system_prompt=>'you are a helpful assistant'
        , host=>%s
        , embedding_options=> jsonb_build_object
          ( 'seed', 42
          , 'temperature', 0.6
          )
        )
    """,
        (ollama_host,),
    )
    actual = cur.fetchone()[0]
    assert "response" in actual and "done" in actual and actual["done"] is True


def test_ollama_generate_no_host(cur_with_ollama_host):
    cur_with_ollama_host.execute("""
        select ai.ollama_generate
        ( 'llama3.2:1b'
        , 'what is the typical weather like in Alabama in June'
        , system_prompt=>'you are a helpful assistant'
        , embedding_options=> jsonb_build_object
          ( 'seed', 42
          , 'temperature', 0.6
          )
        )
    """)
    actual = cur_with_ollama_host.fetchone()[0]
    assert "response" in actual and "done" in actual and actual["done"] is True


def test_ollama_image(cur_with_ollama_host):
    cur_with_ollama_host.execute("""
        select ai.ollama_generate
        ( 'smollm:135m'
        , 'Please describe this image.'
        , images=> array[pg_read_binary_file('/pgai/tests/postgresql-vs-pinecone.jpg')]
        , system_prompt=>'you are a helpful assistant'
        , embedding_options=> jsonb_build_object
          ( 'seed', 42
          , 'temperature', 0.9
          )
        )
    """)
    actual = cur_with_ollama_host.fetchone()[0]
    assert "response" in actual and "done" in actual and actual["done"] is True


def test_ollama_chat_complete(cur, ollama_host):
    cur.execute(
        """
        select ai.ollama_chat_complete
        ( 'llama3.2:1b'
          , jsonb_build_array
            ( jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant')
            , jsonb_build_object('role', 'user', 'content', 'what is the typical weather like in Alabama in June')
            )
          , host=>%s
          , chat_options=> jsonb_build_object
            ( 'seed', 42
            , 'temperature', 0.6
            )
        )
    """,
        (ollama_host,),
    )
    actual = cur.fetchone()[0]
    assert (
        "message" in actual
        and "content" in actual["message"]
        and "done" in actual
        and actual["done"] is True
    )


def test_ollama_chat_complete_no_host(cur_with_ollama_host):
    cur_with_ollama_host.execute("""
        select ai.ollama_chat_complete
        ( 'llama3.2:1b'
          , jsonb_build_array
            ( jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant')
            , jsonb_build_object('role', 'user', 'content', 'what is the typical weather like in Alabama in June')
            )
          , chat_options=> jsonb_build_object
            ( 'seed', 42
            , 'temperature', 0.6
            )
        )
    """)
    actual = cur_with_ollama_host.fetchone()[0]
    assert (
        "message" in actual
        and "content" in actual["message"]
        and "done" in actual
        and actual["done"] is True
    )


def test_ollama_chat_complete_image(cur_with_ollama_host):
    cur_with_ollama_host.execute("""
        select ai.ollama_chat_complete
        ( 'smollm:135m'
        , jsonb_build_array
          ( jsonb_build_object
            ( 'role', 'user'
            , 'content', 'describe this image'
            , 'images', jsonb_build_array(encode(pg_read_binary_file('/pgai/tests/postgresql-vs-pinecone.jpg'), 'base64'))
            )
          )
        , chat_options=> jsonb_build_object
          ( 'seed', 42
          , 'temperature', 0.9
          )
        )->'message'->>'content'
    """)
    actual = cur_with_ollama_host.fetchone()[0]
    assert actual is not None


def test_ollama_ps(cur, ollama_host):
    cur.execute(
        """
        select count(*) filter (where "name" = 'smollm:135m') as actual
        from ai.ollama_ps(host=>%s)
    """,
        (ollama_host,),
    )
    actual = cur.fetchone()[0]
    assert actual > 0


def test_ollama_ps_no_host(cur_with_ollama_host):
    cur_with_ollama_host.execute("""
        select count(*) filter (where "name" = 'smollm:135m') as actual
        from ai.ollama_ps()
    """)
    actual = cur_with_ollama_host.fetchone()[0]
    assert actual > 0
