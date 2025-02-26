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

questions = [
    {
        "type": "select",
        "name": "provider",
        "message": "Which provider would you like to use?",
        "choices": EMBEDDING_MODELS.keys(),
    },
    {
        "type": "password",
        "message": "API key",
        "name": "api_key",
        "when": lambda x: x["provider"] in [COHERE, VOYAGE, OPENAI]
        and os.getenv(API_KEY_NAME[x["provider"]]) is None,
        "validate": lambda v: len(v) > 0,
    },
    {
        "type": "select",
        "message": "Which model would you like to use?",
        "name": "model",
        "choices": lambda x: EMBEDDING_MODELS[x["provider"]],
    },
    {
        "type": "select",
        "message": "How would you like to load a dataset?",
        "name": "dataset",
        "choices": ["huggingface", "new_table", "existing_table"],
    },
    {
        "type": "select",
        "message": "Which huggingface dataset would you like to use?",
        "name": "huggingface_dataset",
        "when": lambda x: x["dataset"] == "huggingface",
        "choices": ["wikipedia", "other", "another other"],
    },
]


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


def setup_dataset(answers, port):
    sql_snippets = {
        "wikipedia": f"""
            select ai.load_dataset(
              'wikipedia'
            , config_name => '20220301.en'
            , kwargs=> '{{"trust_remote_code": true}}'::jsonb
            , table_name => 'wikipedia'
            , batch_size => 100
            , max_batches => 1
            )
        """
    }
    dataset = answers["huggingface_dataset"]
    table = dataset
    if dataset not in sql_snippets.keys():
        print(f"unknown dataset '{dataset}'")
        exit(1)
    with yaspin(text="loading dataset") as sp:
        sql = sql_snippets[answers["huggingface_dataset"]]
        if sql is None:
            sp.write("unknown dataset")
            exit(1)
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


def get_tables(port):
    results = fetchall_sql(
        port,
        "SELECT relname from pg_class where relnamespace = 'public'::regnamespace and relkind = 'r'",
    )
    return [r[0] for r in results]


def setup_vectorizer(answers, port) -> int:

    column_sql = "SELECT attname FROM pg_attribute WHERE attrelid = format('%%I.%%I', 'public', %(table)s::text)::regclass AND attnum >=1 AND NOT attisdropped"

    def get_text_columns(table):
        sql = column_sql + " AND atttypid = 'text'::regtype::oid"
        results = fetchall_sql(port, sql, table=table)
        return [r[0] for r in results]

    def get_columns(table):
        results = fetchall_sql(port, column_sql, table=table)
        return [r[0] for r in results]

    tables = get_tables(port)
    if len(tables) == 0:
        print("no tables in public schema")
        exit(1)
    elif len(tables) == 1:
        table = tables[0]
    else:
        table = questionary.select(
            "Select the table to vectorize", choices=tables
        ).ask()

    columns = get_text_columns(table)
    if len(columns) == 0:
        print(f"no columns of type 'text' in table 'public.{table}'")
        exit(1)
    if len(columns) == 1:
        column = columns[0]
    else:
        column = questionary.select("Select the column to embed", choices=columns).ask()

    configure_formatting = questionary.confirm(
        "Would you like to configure formatting?"
    ).ask()
    if configure_formatting is True:
        choices = get_columns(table)
        choices.remove(column)
        items = questionary.checkbox(
            "Which columns would you like to add to the formatting?", choices=choices
        ).ask()
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
    api_key_name = None
    if provider == COHERE:
        function_args = f"'cohere/{model}', {dims}, api_key_name => 'COHERE_API_KEY'"
    else:
        function_args = f"'{model}', {dims}"

    sql = f"""
        select ai.create_vectorizer(
          '{table}'
        , embedding => ai.{embedding_function}({function_args})
        , chunking => ai.chunking_recursive_character_text_splitter('{column}'){formatting if formatting is not None else ""}{api_key_name if api_key_name is not None else ""}
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
    sql = f"select ai.vectorizer_queue_pending({vectorizer_id}, exact_count => true);"
    with yaspin(text="embedding source table") as sp:
        while True:
            row = fetchone_sql(port, sql)
            count = int(row[0])
            sp.text = f"embedding source table ({count} remaining)"
            if count == 0:
                sp.write("✔ source table embedded")
                break
            time.sleep(1)


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
    if subprocess.run([docker_bin, "compose", "pull"]).returncode != 0:
        print("error while pulling docker images")
        exit(1)


def pull_ollama_model(docker_bin, model):
    if subprocess.run([docker_bin, "compose", "exec", "-ti", "ollama", "ollama", "pull", model]).returncode != 0:
        print("error while pulling ollama model")
        exit(1)


def main():
    docker_bin = shutil.which("docker")
    if docker_bin is None:
        print("docker is not available but is required for pgai vectorizer quickstart")
        print("install docker https://docs.docker.com/desktop/ and try again")
        exit(1)
    if not has_docker_compose(docker_bin):
        print("docker does not have the compose subcommand, but it is required")
        print("install docker compose https://docs.docker.com/compose/ and try again")
        exit(1)

    answers = questionary.prompt(questions)
    provider = answers["provider"]
    api_key = get_api_key(answers)
    if not is_api_key_valid(provider, api_key):
        # TODO: perform this validation earlier (punted because it's not trivial)
        print("The provided API key is invalid")
        exit(1)
    write_compose(provider, api_key)
    pull_images(docker_bin)
    port = start_containers(docker_bin)
    if port is None:
        exit(1)
    if provider == OLLAMA:
        pull_ollama_model(docker_bin, answers["model"])
    create_extension(port)
    setup_dataset(answers, port)
    vectorizer_id = setup_vectorizer(answers, port)
    monitor_embeddings(answers, port, vectorizer_id)


if __name__ == "__main__":
    main()
