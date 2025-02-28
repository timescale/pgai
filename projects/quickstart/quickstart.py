## Note: This is PoC-level code, at best. Most of it probably doesn' work.

import questionary
import shutil
import subprocess
import os

from yaspin import yaspin
import time
from textwrap import dedent, indent
import psycopg
from jinja2 import Environment, PackageLoader, select_autoescape
import cohere
import openai
import voyageai
import atexit
import platform
import requests

env = Environment(
    loader=PackageLoader("quickstart"),
    autoescape=select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)

DB_DOCKER_IMAGE = "timescale/timescaledb-ha:pg17"
VECTORIZER_WORKER_DOCKER_IMAGE = "timescale/pgai-vectorizer-worker:latest"
OLLAMA_DOCKER_IMAGE = "ollama/ollama"

OPENAI = "OpenAI"
COHERE = "Cohere"
VOYAGE = "Voyage AI"
OLLAMA = "Ollama"

EMBEDDING_MODELS = {
    OPENAI: [
        "text-embedding-3-small",
        "text-embedding-3-large",
        "text-embedding-ada-002",
    ],
    COHERE: [
        "embed-english-v3.0",
        "embed-english-light-v3.0",
        "embed-multilingual-v3.0",
        "embed-multilingual-light-v3.0",
    ],
    VOYAGE: ["voyage-3-large", "voyage-3", "voyage-3-lite"],
    OLLAMA: [
        "all-minilm",
        "nomic-embed-text",
        "mxbai-embed-large",
        "snowflake-arctic-embed",
    ],
}

# Note: These durations were experimentally determined on the wikipedia
# dataset, which consists of 4_191_464 characters in 6267 chunks.
WIKIPEDIA_EMBEDDING_DURATION_SECONDS = {
    "voyage-3-large": 90,
    "voyage-3": 90,
    "voyage-3-lite": 90,
    "text-embedding-3-large": 50,
    "text-embedding-3-small": 50,
    "text-embedding-ada-002": 50,
    "embed-english-v3.0": 30,
    "embed-english-light-v3.0": 20,
    "embed-multilingual-v3.0": 30,
    "embed-multilingual-light-v3.0": 20,
    "all-minilm": None,
    "nomic-embed-text": None,
    "mxbai-embed-large": None,
    "snowflake-arctic-embed": None,
}

DIMENSIONS = {
    "text-embedding-3-large": 1536,
    "text-embedding-3-small": 1536,
    "text-embedding-ada-002": 1536,
    "embed-english-v3.0": 1024,
    "embed-english-light-v3.0": 384,
    "embed-multilingual-v3.0": 1024,
    "embed-multilingual-light-v3.0": 384,
    "voyage-3-large": 1024,
    "voyage-3": 1024,
    "voyage-3-lite": 512,
    "nomic-embed-text": 768,
    "mxbai-embed-large": 1024,
    "snowflake-arctic-embed": 1024,
    "all-minilm": 384,
}

EMBEDDING_FUNCTIONS = {
    OPENAI: "embedding_openai",
    COHERE: "embedding_litellm",
    VOYAGE: "embedding_voyageai",
    OLLAMA: "embedding_ollama",
}

API_KEY_NAME = {
    OPENAI: "OPENAI_API_KEY",
    COHERE: "COHERE_API_KEY",
    VOYAGE: "VOYAGE_API_KEY",
    OLLAMA: None,
}

OLLAMA_SIZE_ARCH = {
    "linux/amd64": "1.5GB",
    "linux/arm64": "2.3GB",
}

OLLAMA_MODEL_SIZE = {
    "all-minilm": "46MB",
    "nomic-embed-text": "274MB",
    "mxbai-embed-large": "670MB",
    "snowflake-arctic-embed": "670MB",
}

METADATA = {
    "version": "0",  # NOTE: Increment this whenever the metadata structure changes materially
}

TELEMETRY = {
    "program": "pgai-quickstart",
    "version": "pre-release",  # XXX: replace this before merging
    "success": False,
    "duration": None,
    "metadata": METADATA,
    "os_family": os.name,
    "os": platform.system(),
    "arch": platform.machine(),
}

TELEMETRY_SUBMITTED = False

PROGRAM_START = time.time()

EXIT_CODE = None
EXIT_REASON = None


def exit_quickstart(code: int, reason: str):
    global EXIT_CODE, EXIT_REASON
    EXIT_CODE = code
    EXIT_REASON = reason
    if code > 0:
        print(reason)
    exit(code)


def provider_title(provider: str) -> str:
    if provider != OLLAMA:
        return provider
    arch = str(
        subprocess.run(
            [
                shutil.which("docker"),
                "version",
                "--format",
                "{{.Server.Os}}/{{.Server.Arch}}",
            ],
            capture_output=True,
            text=True,
        ).stdout
    ).strip()
    if arch not in OLLAMA_SIZE_ARCH:
        print(arch)
        return "Ollama"
    return f"Ollama (requires {OLLAMA_SIZE_ARCH[arch]} download)"


def model_title(model: str) -> str:
    if model in OLLAMA_MODEL_SIZE:
        return f"{model} ({OLLAMA_MODEL_SIZE[model]})"
    return model


def validate():
    models = [model for models in EMBEDDING_MODELS.values() for model in models]
    for model in models:
        assert model in WIKIPEDIA_EMBEDDING_DURATION_SECONDS, (
            f"no embedding duration for model '{model}'"
        )
        assert model in DIMENSIONS, f"no dimension for model '{model}'"


def has_docker_compose(docker_bin) -> bool:
    if subprocess.run([docker_bin, "help"], capture_output=True).returncode != 0:
        return False
    if (
        subprocess.run([docker_bin, "help", "compose"], capture_output=True).returncode
        != 0
    ):
        return False
    return True


def generate_docker_compose(provider, api_key):
    api_key_name = API_KEY_NAME[provider]
    use_ollama = provider == OLLAMA
    template = env.get_template("compose.yml.j2")
    return template.render(
        provider=provider,
        api_key_name=api_key_name,
        api_key=api_key,
        use_ollama=use_ollama,
        db_docker_image=DB_DOCKER_IMAGE,
        vectorizer_worker_docker_image=VECTORIZER_WORKER_DOCKER_IMAGE,
        ollama_docker_image=OLLAMA_DOCKER_IMAGE,
    )


def check_db_connectivity(docker_bin):
    count = 0
    success_count = 0
    while count < 5:
        if (
            subprocess.run(
                [docker_bin, "compose", "exec", "db", "pg_isready"], capture_output=True
            ).returncode
            == 0
        ):
            success_count += 1
        if success_count == 2:
            return True
        count += 1
        time.sleep(0.5)
    if count == 5:
        return False


def write_compose(provider, api_key):
    docker_compose = generate_docker_compose(provider, api_key)
    with yaspin(text="writing compose.yml") as sp:
        with open("compose.yml", "w", encoding="utf-8") as f:
            f.write(docker_compose)
        sp.write("✔ wrote compose.yml")


def start_containers(docker_bin):
    port = None
    with yaspin(text="starting containers") as sp:
        result = subprocess.run(
            [docker_bin, "compose", "up", "-d"], capture_output=True
        )
        if result.returncode == 0:
            sp.write("✔ started containers")
        else:
            sp.write("unable to start containers")
            return None
        result = subprocess.run(
            [docker_bin, "compose", "port", "db", "5432"], capture_output=True
        )
        if result.returncode != 0:
            sp.write("unable to obtain db port")
            sp.write(result.stderr)
            return None
        port = result.stdout.decode("utf-8").strip()
        sp.text = "checking db connectivity"
        if check_db_connectivity(docker_bin):
            sp.write("✔ db listening")
        else:
            sp.write("db not up")
            return None
    return port


def execute_sql(port, sql, **kwargs):
    with psycopg.connect(f"postgres://postgres:postgres@{port}") as conn:
        return conn.execute(sql, kwargs)


def fetchone_sql(port, sql, **kwargs):
    with psycopg.connect(f"postgres://postgres:postgres@{port}") as conn:
        return conn.execute(sql, kwargs).fetchone()


def fetchall_sql(port, sql, **kwargs):
    with psycopg.connect(f"postgres://postgres:postgres@{port}") as conn:
        return conn.execute(sql, kwargs).fetchall()


def create_extension(port):
    with yaspin(text="creating extension") as sp:
        sql = "CREATE EXTENSION IF NOT EXISTS ai CASCADE;"
        sp.write(f"running '{sql}'")
        sp.text = "creating extension"
        execute_sql(port, sql)
        sp.write("✔ extension created")


def setup_dataset(dataset, port):
    sql_snippets = {
        "wikipedia": """
            select ai.load_dataset(
              'wikipedia'
            , config_name => '20220301.en'
            , kwargs=> '{"trust_remote_code": true}'::jsonb
            , table_name => 'wikipedia'
            , batch_size => 100
            , max_batches => 1
            )
        """
    }
    table = dataset
    if dataset not in sql_snippets.keys():
        exit_quickstart(1, f"unknown dataset '{dataset}'")
    start = time.time()
    with yaspin(text="loading dataset") as sp:
        sql = sql_snippets[dataset]
        if table in get_tables(port):
            sp.write(f"table '{table}' already exists")
            sp.text = f"dropping table '{table}'"
            execute_sql(port, f"DROP TABLE {table} CASCADE")
            sp.write(f"✔ table '{table}' dropped")

        sp.write(f"running query:\n{indent(dedent(sql), '    ')}")
        sp.text = "loading dataset"
        execute_sql(port, sql)
        execute_sql(port, f"alter table {table} add primary key (id)")
        sp.write("✔ dataset loaded")
    METADATA["dataset_loading_duration_seconds"] = time.time() - start


def get_tables(port):
    results = fetchall_sql(
        port,
        "SELECT relname from pg_class where relnamespace = 'public'::regnamespace and relkind = 'r' and relname not in (SELECT target_table FROM ai.vectorizer)",
    )
    return [r[0] for r in results]


def setup_vectorizer(answers, port) -> int:
    VECTORIZER_METADATA = {}
    METADATA["vectorizer"] = VECTORIZER_METADATA

    column_sql = "SELECT attname FROM pg_attribute WHERE attrelid = format('%%I.%%I', 'public', %(table)s::text)::regclass AND attnum >=1 AND NOT attisdropped"
    vectorizer_sql = (
        "SELECT view_name FROM ai.vectorizer WHERE source_table = %(table)s::text"
    )

    def get_text_columns(table):
        sql = column_sql + " AND atttypid = 'text'::regtype::oid"
        results = fetchall_sql(port, sql, table=table)
        return [r[0] for r in results]

    def get_columns(table):
        results = fetchall_sql(port, column_sql, table=table)
        return [r[0] for r in results]

    def get_existing_vectorizer_names(table, port) -> list[str]:
        results = fetchall_sql(port, vectorizer_sql, table=table)
        return [r[0] for r in results]

    print("The dataset is loaded")

    tables = get_tables(port)
    table = None
    if len(tables) == 0:
        exit_quickstart(1, "no tables in public schema")
    else:
        table = questionary.select(
            "Select the table to vectorize", choices=tables
        ).unsafe_ask()
    VECTORIZER_METADATA["table"] = table

    vectorizers = get_existing_vectorizer_names(table, port)
    destination = None
    if len(vectorizers) > 0:
        print(f"The table '{table}' already has a vectorizer ({vectorizers})")
        name = questionary.text(
            "Provide a name for this vectorizer",
            validate=lambda x: x not in vectorizers,
        ).unsafe_ask()
        destination = f"\n        , destination => '{name}'"
        VECTORIZER_METADATA["destination"] = name

    columns = get_text_columns(table)
    column = None
    if len(columns) == 0:
        exit_quickstart(1, f"no columns of type 'text' in table 'public.{table}'")
    else:
        column = questionary.select(
            "Select the column to embed", choices=columns
        ).unsafe_ask()
    VECTORIZER_METADATA["column"] = column

    print(
        f"The vectorizer splits the content of the '{column}' columns into smaller pieces\n"
        'or "chunks" when it is too large. This improves retrieval accuracy, but means \n'
        "that important information (context) can be lost.\n"
        'The vectorizer\'s "formatting" configuration allows you to add context from the\n'
        "source row into the chunk, by e.g. inserting the title of the document into every\n"
        "chunk."
    )
    configure_formatting = questionary.confirm(
        "Would you like to configure formatting?"
    ).unsafe_ask()
    VECTORIZER_METADATA["configure_formatting"] = configure_formatting
    if configure_formatting is True:
        choices = get_columns(table)
        choices.remove(column)
        items = questionary.checkbox(
            "Which columns would you like to add to the formatting?", choices=choices
        ).unsafe_ask()
        VECTORIZER_METADATA["formatting_column_count"] = len(items)
        items.append("chunk")
        formatting = (
            "\n        , formatting => ai.formatting_python_template('"
            + " ".join([f"{i}: ${i}" for i in items])
            + "')"
        )
    else:
        formatting = None

    provider = answers["provider"]
    embedding_function = EMBEDDING_FUNCTIONS[provider]
    model = answers["model"]
    dims = DIMENSIONS[model]
    if provider == COHERE:
        function_args = f"'cohere/{model}', {dims}, api_key_name => 'COHERE_API_KEY'"
    else:
        function_args = f"'{model}', {dims}"

    additional_bits = "".join(
        [bit for bit in [formatting, destination] if bit is not None]
    )

    sql = f"""
        select ai.create_vectorizer(
          '{table}'
        , embedding => ai.{embedding_function}({function_args})
        , chunking => ai.chunking_recursive_character_text_splitter('{column}'){additional_bits}
        );
    """
    with yaspin(text="creating vectorizer") as sp:
        sp.write(f"running query:\n{indent(dedent(sql), '    ')}")
        sp.text = "creating vectorizer"
        row = fetchone_sql(port, sql)
        vectorizer_id = int(row[0])
        sp.write("✔ vectorizer created")
    return vectorizer_id


def monitor_embeddings(answers, port, vectorizer_id):
    MONITOR_METADATA = {}
    METADATA["monitor"] = MONITOR_METADATA
    provider = answers["provider"]
    model = answers["model"]
    sql = f"select ai.vectorizer_queue_pending({vectorizer_id}, exact_count => true);"
    if provider == OLLAMA:
        print("embedding source table, this could take a very long time")
        duration_seconds = None
    else:
        duration_seconds = WIKIPEDIA_EMBEDDING_DURATION_SECONDS[model]
    MONITOR_METADATA["estimated_embedding_duration_seconds"] = duration_seconds
    start = time.time()
    with yaspin(text="embedding source table") as sp:
        while True:
            row = fetchone_sql(port, sql)
            count = int(row[0])
            if duration_seconds is None:
                remaining = ""
            else:
                duration_seconds -= 1
                if duration_seconds < -10:
                    remaining = ", taking longer than usual"
                elif duration_seconds < 0:
                    remaining = f", approx. {0}s"
                else:
                    remaining = f", approx. {duration_seconds:.0f}s"
            sp.text = f"embedding source table ({count} rows remaining{remaining})"
            if count == 0:
                sp.write("✔ source table embedded")
                break
            time.sleep(1)
    MONITOR_METADATA["actual_embedding_duration_seconds"] = time.time() - start


def is_api_key_valid(provider, api_key):
    if provider == OLLAMA:
        return True
    if provider == OPENAI:
        client = openai.OpenAI(api_key=api_key)
        try:
            client.models.list()
            return True
        except openai.AuthenticationError:
            return False
    elif provider == VOYAGE:
        client = voyageai.Client(api_key=api_key)
        model = "voyage-3-lite"
        try:
            client.embed(["test"], model=model)
            return True
        except voyageai.error.AuthenticationError:
            return False
    elif provider == COHERE:
        client = cohere.Client(api_key=api_key)
        try:
            client.models.list()
            return True
        except cohere.errors.unauthorized_error.UnauthorizedError:
            return False
    else:
        raise RuntimeError(f"Unexpected provider {provider}")


def get_api_key(answers):
    provider = answers["provider"]
    if provider == OLLAMA:
        return None
    return answers.get("api_key", None) or os.getenv(API_KEY_NAME[provider], None)


def pull_images(docker_bin):
    print("pulling required docker images")
    if subprocess.run([docker_bin, "compose", "pull"]).returncode != 0:
        exit_quickstart(1, "error while pulling docker images")


def pull_ollama_model(docker_bin, model):
    print(f"pulling ollama model '{model}'")
    start = time.time()
    if (
        subprocess.run(
            [docker_bin, "compose", "exec", "-ti", "ollama", "ollama", "pull", model]
        ).returncode
        != 0
    ):
        exit_quickstart(1, "error while pulling ollama model")
    METADATA["ollama_model_pull_duration_seconds"] = time.time() - start


def ask_initial_questions():
    answers = {}
    provider = questionary.select(
        "Which embedding model provider would you like to use?",
        choices=[
            questionary.Choice(title=provider_title(k), value=k)
            for k in EMBEDDING_MODELS.keys()
        ],
    ).unsafe_ask()
    answers["provider"] = provider
    METADATA["provider"] = provider
    api_key = None
    env_has_key = os.getenv(API_KEY_NAME[provider]) is not None
    METADATA["api_key_source"] = "environment" if env_has_key else "user"
    if provider in [COHERE, VOYAGE, OPENAI] and not env_has_key:
        api_key = questionary.password(
            "API Key", validate=lambda v: len(v) > 0
        ).unsafe_ask()
    answers["api_key"] = api_key

    if not is_api_key_valid(provider, get_api_key(answers)):
        # TODO: loop to get valid API key
        error_msg = "The provided API key is invalid"
        exit_quickstart(1, error_msg)

    model = questionary.select(
        "Which model would you like to use?",
        choices=[
            questionary.Choice(title=model_title(k), value=k)
            for k in EMBEDDING_MODELS[provider]
        ],
    ).unsafe_ask()
    answers["model"] = model
    METADATA["model"] = model
    dataset = questionary.select(
        "Which dataset would you like to use?",
        choices=["wikipedia", "other", "another other"],
    ).unsafe_ask()
    answers["dataset"] = dataset
    METADATA["dataset"] = dataset
    return answers


def main():
    docker_bin = shutil.which("docker")
    if docker_bin is None:
        print("install docker https://docs.docker.com/desktop/ and try again")
        exit_quickstart(
            1, "docker is not available but is required for pgai vectorizer quickstart"
        )
    if not has_docker_compose(docker_bin):
        print("install docker compose https://docs.docker.com/compose/ and try again")
        exit_quickstart(
            1, "docker does not have the compose subcommand, but it is required"
        )

    print("Welcome to the pgai vectorizer quickstart!")
    print("The quickstart guides you through creating your first vectorizer")
    print("This includes:")
    print("- setting up a database")
    print("- getting some data into your database")
    print("- integrating with a vector embedding provider")
    print("- configuring the vectorizer")
    print("- creating vector embeddings of your sample data")
    print()

    questionary.press_any_key_to_continue().unsafe_ask()

    answers = ask_initial_questions()
    provider = answers["provider"]

    api_key = get_api_key(answers)
    write_compose(provider, api_key)
    pull_images(docker_bin)
    port = start_containers(docker_bin)
    if port is None:
        exit_quickstart(1, "container not started")
    if provider == OLLAMA:
        pull_ollama_model(docker_bin, answers["model"])
    create_extension(port)
    dataset = answers.get("dataset", None)
    if dataset is not None:
        setup_dataset(dataset, port)
    vectorizer_id = setup_vectorizer(answers, port)
    monitor_embeddings(answers, port, vectorizer_id)


def telemetry():
    if os.getenv("DO_NOT_TRACK", None) is not None:
        # If DO_NOT_TRACK is set in any way, no telemetry
        return
    global TELEMETRY_SUBMITTED
    if TELEMETRY_SUBMITTED:
        # somewhat paranoid check that we don't accidentally submit telemetry twice
        return
    TELEMETRY["duration"] = time.time() - PROGRAM_START
    TELEMETRY["success"] = EXIT_CODE is None
    METADATA["error"] = EXIT_REASON

    try:
        TELEMETRY_SUBMITTED = True
        requests.post("https://telemetry.timescale.com/v1/executions", json=TELEMETRY)
    except BaseException:
        # swallow any errors here
        pass


if __name__ == "__main__":
    atexit.register(telemetry)
    validate()
    try:
        main()
    except BaseException as e:
        exit_quickstart(1, str(e))
