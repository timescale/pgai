## Note: This is PoC-level code, at best. Most of it probably doesn' work.
import traceback
from dataclasses import dataclass, field
from typing import Set

import questionary
import shutil
import subprocess
import os

from psycopg import sql
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
from tabulate import tabulate


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

# Note: These durations were experimentally determined on the pgai-docs dataset.
PGAI_DOCS_EMBEDDING_DURATION_SECONDS = {
    "voyage-3-large": 10,
    "voyage-3": 10,
    "voyage-3-lite": 10,
    "text-embedding-3-large": 13,
    "text-embedding-3-small": 13,
    "text-embedding-ada-002": 13,
    "embed-english-v3.0": 10,
    "embed-english-light-v3.0": 10,
    "embed-multilingual-v3.0": 10,
    "embed-multilingual-light-v3.0": 10,
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

EMBEDDING_CONFIG_FUNCTIONS = {
    OPENAI: "embedding_openai",
    COHERE: "embedding_litellm",
    VOYAGE: "embedding_voyageai",
    OLLAMA: "embedding_ollama",
}

EMBEDDING_FUNCTIONS = {
    OPENAI: "openai_embed",
    COHERE: "litellm_embed",
    VOYAGE: "voyageai_embed",
    OLLAMA: "ollama_embed",
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


@dataclass
class EmbeddingModelConfig:
    provider: str
    api_key: str
    model: str


def exit_quickstart(code: int, reason: str | BaseException):
    global EXIT_CODE, EXIT_REASON
    EXIT_CODE = code
    EXIT_REASON = reason
    if code > 0:
        if isinstance(reason, BaseException):
            traceback.print_exception(reason)
        else:
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
        assert model in PGAI_DOCS_EMBEDDING_DURATION_SECONDS, (
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


def generate_docker_compose(emcs: list[EmbeddingModelConfig]):
    use_ollama = any([emc.provider == OLLAMA for emc in emcs])
    api_keys = {
        API_KEY_NAME[emc.provider]: emc.api_key
        for emc in emcs
        if emc.provider != OLLAMA
    }
    template = env.get_template("compose.yml.j2")
    return template.render(
        api_keys=api_keys,
        api_key_names=API_KEY_NAME,
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


def write_compose(emcs: list[EmbeddingModelConfig]):
    docker_compose = generate_docker_compose(emcs)
    with yaspin(text="writing compose.yml", color="green") as sp:
        with open("compose.yml", "w", encoding="utf-8") as f:
            f.write(docker_compose)
        sp.ok("✔")


def start_containers(docker_bin):
    with yaspin(text="starting containers", color="green") as sp:
        result = subprocess.run(
            [docker_bin, "compose", "up", "-d"], capture_output=True
        )
        if result.returncode == 0:
            sp.ok("✔")
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
            sp.ok("✔")
        else:
            sp.write("db not up")
            return None
    return port


def create_extension(conn):
    with yaspin(text="creating extension", color="green") as sp:
        sql = "CREATE EXTENSION IF NOT EXISTS ai CASCADE;"
        sp.write(f"running '{sql}'")
        sp.text = "creating extension"
        conn.execute(sql)
        sp.ok("✔")


def setup_pgai_docs_dataset(conn):
    table = "pgai_docs"
    start = time.time()
    with yaspin(text="loading dataset", color="green") as sp:
        sql = "SELECT ai.load_dataset('timescale/pgai-docs', table_name => 'pgai_docs')"
        if table in get_tables(conn):
            sp.write(f"table '{table}' already exists")
            sp.text = f"dropping table '{table}'"
            conn.execute(f"DROP TABLE {table} CASCADE")
            sp.ok("✔")

        sp.write(f"running query:\n{indent(dedent(sql), '    ')}")
        sp.text = "loading dataset"
        conn.execute(sql)
        conn.execute(f"alter table {table} add primary key (path)")
        sp.ok("✔")
    METADATA["dataset_loading_duration_seconds"] = time.time() - start


def get_tables(conn):
    sql = """
        SELECT relname
        FROM pg_class
        WHERE relnamespace = 'public'::regnamespace
          AND relkind = 'r'
          AND relname not in (SELECT target_table FROM ai.vectorizer)
    """
    results = conn.execute(sql).fetchall()
    return [r[0] for r in results]


def setup_vectorizer(emc: EmbeddingModelConfig, conn) -> int:
    VECTORIZER_METADATA = {}
    METADATA["vectorizer"] = VECTORIZER_METADATA

    column_sql = "SELECT attname FROM pg_attribute WHERE attrelid = format('%%I.%%I', 'public', %(table)s::text)::regclass AND attnum >=1 AND NOT attisdropped"
    vectorizer_sql = (
        "SELECT view_name FROM ai.vectorizer WHERE source_table = %(table)s::text"
    )

    def get_text_columns(table):
        sql = column_sql + " AND atttypid = 'text'::regtype::oid"
        results = conn.execute(sql, {"table": table}).fetchall()
        return [r[0] for r in results]

    def get_columns(table):
        results = conn.execute(column_sql, {"table": table}).fetchall()
        return [r[0] for r in results]

    def get_existing_vectorizer_names(table, conn) -> list[str]:
        results = conn.execute(vectorizer_sql, {"table": table}).fetchall()
        return [r[0] for r in results]

    print("The dataset is loaded")

    tables = get_tables(conn)
    table = None
    if len(tables) == 0:
        exit_quickstart(1, "no tables in public schema")
    else:
        table = questionary.select(
            "Select the table to vectorize", choices=tables
        ).unsafe_ask()
    VECTORIZER_METADATA["table"] = table

    vectorizers = get_existing_vectorizer_names(table, conn)
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

    provider = emc.provider
    embedding_function = EMBEDDING_CONFIG_FUNCTIONS[provider]
    model = emc.model
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
    with yaspin(text="creating vectorizer", color="green") as sp:
        sp.write(f"running query:\n{indent(dedent(sql), '    ')}")
        sp.text = "creating vectorizer"
        row = conn.execute(sql).fetchone()
        vectorizer_id = int(row[0])
        sp.ok("✔")
    return vectorizer_id


def monitor_embeddings(emc, conn, vectorizer_id):
    MONITOR_METADATA = {}
    METADATA["monitor"] = MONITOR_METADATA
    provider = emc.provider
    model = emc.model
    sql = f"select ai.vectorizer_queue_pending({vectorizer_id}, exact_count => true);"
    if provider == OLLAMA:
        print("embedding source table, this could take a very long time")
        duration_seconds = None
    else:
        duration_seconds = PGAI_DOCS_EMBEDDING_DURATION_SECONDS[model]
    MONITOR_METADATA["estimated_embedding_duration_seconds"] = duration_seconds
    start = time.time()
    with yaspin(text="embedding source table", color="green") as sp:
        while True:
            row = conn.execute(sql).fetchone()
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
                sp.ok("✔")
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


def ask_vectorizer_questions() -> EmbeddingModelConfig:
    provider = questionary.select(
        "Which embedding model provider would you like to use?",
        choices=[
            questionary.Choice(title=provider_title(k), value=k)
            for k in EMBEDDING_MODELS.keys()
        ],
    ).unsafe_ask()
    api_key = None
    env_has_key = os.getenv(API_KEY_NAME[provider]) is not None
    METADATA["api_key_source"] = "environment" if env_has_key else "user"
    if provider in [COHERE, VOYAGE, OPENAI]:
        if env_has_key:
            api_key = os.getenv(API_KEY_NAME[provider], None)
        else:
            api_key = questionary.password(
                "API Key", validate=lambda v: len(v) > 0
            ).unsafe_ask()

    if not is_api_key_valid(provider, api_key):
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
    return EmbeddingModelConfig(provider=provider, api_key=api_key, model=model)


def get_vectorizer_details(conn, vectorizer_id):
    vectorizer_details_sql = """
        SELECT
          source_schema
        , source_table
        , target_schema
        , target_table
        , view_schema
        , view_name as embedding_view
        FROM ai.vectorizer
        WHERE vectorizer.id = %(vectorizer_id)s
    """
    return conn.execute(
        vectorizer_details_sql, {"vectorizer_id": vectorizer_id}
    ).fetchone()


def showcase_embeddings(conn, vectorizer_id):
    source_schema, source_table, target_schema, target_table, view_schema, view_name = (
        get_vectorizer_details(conn, vectorizer_id)
    )
    print(
        f"The data in the source table '{source_schema}.{source_table}' is now chunked and embedded"
    )
    print(
        f"The chunks and corresponding embeddings are stored in the '{target_schema}.{target_table}' table"
    )
    print(
        f"For convenience, the '{view_schema}.{view_name}' view joins the source table with its embeddings"
    )
    print()


@dataclass
class QuickstartState:
    providers: Set[str] = field(default_factory=set)
    emcs: list[EmbeddingModelConfig] = field(default_factory=list)
    dataset_loaded: bool = False
    docker_bin: str | None = None
    docker_host: str | None = None
    vectorizer_id_to_emc: dict[int, EmbeddingModelConfig] = field(default_factory=dict)


def similarity_search(state: QuickstartState):
    conn = psycopg.connect(
        f"postgres://postgres:postgres@{state.docker_host}", autocommit=True
    )

    if len(state.vectorizer_id_to_emc.keys()) > 1:
        vectorizers = conn.execute("SELECT id, view_name FROM ai.vectorizer").fetchall()
        vectorizer_id = questionary.select(
            "Which vectorizer would you like to use for similarity search",
            choices=[
                questionary.Choice(title=view_name, value=id)
                for id, view_name in vectorizers
            ],
        ).unsafe_ask()
    else:
        vectorizer_id = list(state.vectorizer_id_to_emc.keys())[0]

    emc = state.vectorizer_id_to_emc[vectorizer_id]
    _, _, _, _, view_schema, view_name = get_vectorizer_details(conn, vectorizer_id)

    print(
        "Similarity search is about finding documents which are semantically similar to a query string."
    )
    print(
        "To find similar documents, you compute the vector distance using pgvector's '<=>' operator"
    )
    print(
        "For example, the following query gets the top 10 chunks most similar to the input vector:"
    )
    print(f"""
        SELECT
          title
        , chunk
        , embedding <=> '<input vector>'::vector as distance
        FROM {view_schema}.{view_name}
        ORDER BY 2
        LIMIT 10
    """)
    print("Let's see an example based on the pgai documentation")
    print("The pgai documentation covers a few core topics")

    VECTORIZER_OPENAI = "pgai vectorizer with OpenAI"
    CHAT_COMPLETION = "pgai chat completion"
    PGAI_EXTENSION_INSTALL = "pgai extension installation"

    chosen = questionary.select(
        "Select a topic for which you would like to perform similarity search:",
        choices=[VECTORIZER_OPENAI, CHAT_COMPLETION, PGAI_EXTENSION_INSTALL],
    ).unsafe_ask()
    if chosen == VECTORIZER_OPENAI:
        query = "Set up a vectorizer with OpenAI"
    elif chosen == CHAT_COMPLETION:
        query = "Perform chat completion using OpenAI"
    else:
        query = "pgai extension installation instructions"

    dimensions_sql = (
        sql.SQL(", dimensions => %(dimensions)s")
        if emc.model == "text-embedding-3-large"
        else sql.SQL("")
    )

    simple_similarity_search_sql = sql.SQL("""
        SELECT
          title
        , chunk_seq
        , substring(chunk for 20) || '...' as chunk_snippet
        , embedding <=> ai.{}(%(model)s, %(query)s{}) as distance
        FROM {}.{}
        ORDER BY 4
        LIMIT 10
    """).format(
        sql.Identifier(EMBEDDING_FUNCTIONS[emc.provider]),
        dimensions_sql,
        sql.Identifier(view_schema),
        sql.Identifier(view_name),
    )

    params = {"model": emc.model, "query": query, "dimensions": DIMENSIONS[emc.model]}
    cur = psycopg.ClientCursor(conn)
    print(cur.mogrify(simple_similarity_search_sql, params))
    results = conn.execute(simple_similarity_search_sql, params).fetchall()

    print(
        tabulate(results, headers=["title", "chunk_seq", "chunk_snippet", "distance"])
    )
    print("")

    print("That was a good start, but to find the top matching documents (not chunks),")
    print("we need to do some aggregation")
    questionary.press_any_key_to_continue().unsafe_ask()

    similarity_search_sql = sql.SQL("""
        WITH document_min_chunk_distances AS (
           SELECT
             title
           , min(embedding <=> ai.{}(%(model)s, %(query)s{})) AS distance
           FROM {}.{}
           GROUP BY title
        )
        SELECT rank() OVER (ORDER BY distance) AS rank, title, distance
        FROM document_min_chunk_distances
        ORDER BY 1
        LIMIT 5;
    """).format(
        sql.Identifier(EMBEDDING_FUNCTIONS[emc.provider]),
        dimensions_sql,
        sql.Identifier(view_schema),
        sql.Identifier(view_name),
    )
    cur = psycopg.ClientCursor(conn)
    print(cur.mogrify(similarity_search_sql, params))
    results = conn.execute(similarity_search_sql, params).fetchall()

    print(tabulate(results, headers=["rank", "title", "distance"]))
    print("")


def create_vectorizer(state: QuickstartState):
    emc = ask_vectorizer_questions()
    state.emcs.append(emc)
    if emc.provider not in state.providers:
        state.providers.add(emc.provider)
        write_compose(state.emcs)
        pull_images(state.docker_bin)
        port = start_containers(state.docker_bin)
        if port is None:
            exit_quickstart(1, "container not started")
        state.docker_host = port
        if emc.provider == OLLAMA:
            pull_ollama_model(state.docker_bin, emc.model)

    with psycopg.connect(
        f"postgres://postgres:postgres@{state.docker_host}", autocommit=True
    ) as conn:
        create_extension(conn)
        if not state.dataset_loaded:
            setup_pgai_docs_dataset(conn)
            state.dataset_loaded = True
        vectorizer_id = setup_vectorizer(emc, conn)
        state.vectorizer_id_to_emc[vectorizer_id] = emc
        monitor_embeddings(emc, conn, vectorizer_id)
        showcase_embeddings(conn, vectorizer_id)


def main():
    state = QuickstartState()

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

    state.docker_bin = docker_bin

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

    create_vectorizer(state)

    SIMILARITY_SEARCH = "Run a basic similarity search"
    CREATE_ANOTHER = "Create another vectorizer"
    EXIT = "Exit"
    choices = [SIMILARITY_SEARCH, CREATE_ANOTHER, EXIT]
    while True:
        chosen = questionary.select(
            "What would you like to do next?",
            choices=choices,
        ).unsafe_ask()
        if chosen == SIMILARITY_SEARCH:
            similarity_search(state)
        elif chosen == CREATE_ANOTHER:
            create_vectorizer(state)
        else:
            print("Thank you for using the pgai quickstart, have fun!")
            exit_quickstart(0, "done")


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
    except SystemExit as e:
        raise e
    except BaseException as e:
        exit_quickstart(1, e)
