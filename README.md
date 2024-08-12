
<p></p>
<div align=center>

# pgai

<h3>pgai brings AI workflows to your PostgreSQL database</h3>

[![Discord](https://img.shields.io/badge/Join_us_on_Discord-black?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/KRdHVXAmkp)
[![Try Timescale for free](https://img.shields.io/badge/Try_Timescale_for_free-black?style=for-the-badge&logo=timescale&logoColor=white)](https://tsdb.co/gh-pgai-signup)
</div>

pgai simplifies the process of building [search](https://en.wikipedia.org/wiki/Similarity_search), and
[Retrieval Augmented Generation](https://en.wikipedia.org/wiki/Prompt_engineering#Retrieval-augmented_generation) (RAG) AI applications with PostgreSQL.

pgai brings embedding and generation AI models closer to the database. With pgai, you can now do the following directly from within PostgreSQL in a SQL query:

* Create vector [embeddings](#embed) for your data.
* Retrieve LLM [chat completions](#chat-complete) from models like Claude Sonnet 3.5, OpenAI GPT4o, Cohere Command, and Llama 3 (via Ollama).
* Reason over your data and facilitate use cases like [classification, summarization, and data enrichment](docs/advanced.md) on your existing relational data in PostgreSQL.

Here's how to get started with pgai:

* **Everyone**: Use pgai in your PostgreSQL database.
  1. [Install pgai](#installation).
  1. Use pgai to integrate AI from your provider:
    * [Ollama](./docs/ollama.md) - configure pgai for Ollama, then use the model to embed, chat complete and generate.
    * [OpenAI](./docs/openai.md) - configure pgai for OpenAI, then use the model to tokenize, embed, chat complete and moderate. This page also includes advanced examples.
    * [Anthropic](./docs/anthropic.md) - configure pgai for Anthropic, then use the model to generate content.
    * [Cohere](./docs/cohere.md) - configure pgai for Cohere, then use the model to tokenize, embed, chat complete, classify, and rerank.
* **Extension contributor**: Contribute to pgai and improve the project.
  * [Develop and test changes to the pgai extension](./DEVELOPMENT.md).
  * See the [Issues tab](https://github.com/timescale/pgai/issues) for a list of feature ideas to contribute.

**Learn more about pgai:** To learn more about the pgai extension and why we built it, read this blog post [pgai: Giving PostgreSQL Developers AI Engineering Superpowers](http://www.timescale.com/blog/pgai-giving-postgresql-developers-ai-engineering-superpowers).

## Installation

The fastest ways to run PostgreSQL with the pgai extension are to:

1. Create your database environment. Either:
   * [Use a pre-built Docker container](#use-a-pre-built-docker-container).
   * [Use a Timescale Cloud service](#use-a-timescale-cloud-service).
   * [Install from source](#install-from-source).

2. [Enable the pgai extension](#enable-the-pgai-extension-in-your-database).

3. [Use pgai](#use-pgai).

### Use a pre-built Docker container

[Run the TimescaleDB Docker image](https://docs.timescale.com/self-hosted/latest/install/installation-docker/), then
[enable the pgai extension](#enable-the-pgai-extension-in-your-database).

### Use a Timescale Cloud service

pgai is available for [new][create-a-new-service] or existing Timescale Cloud services. For any service,
[enable the pgai extension](#enable-the-pgai-extension-in-your-database).


### Install from source

To install pgai from source on a PostgreSQL server:

1. **Install the prerequisite software system-wide**
   - **Python3**: if running `python3 --version` in Terminal returns `command
     not found`, download and install the latest version of [Python3][python3].

   - **Pip**: if running `pip --version` in Terminal returns `command not found`:
     - **Standard installation**: use one of the pip [supported methods][pip].
     - **Virtual environment**: usually, pip is automatically installed if you are working in a
       [Python virtual environment][python-virtual-environment]. If you are running PostgreSQL in a virtual
       environment, pgai requires several python packages. Set the `PYTHONPATH` and `VIRTUAL_ENV`
       environment variables before you start your PostgreSQL server.

       ```bash
       PYTHONPATH=/path/to/venv/lib/python3.12/site-packages \
       VIRTUAL_ENV=/path/to/venv \
       pg_ctl -D /path/to/data -l logfile start
       ```
   - **PL/Python**: follow [How to install Postgres 16 with plpython3u: Recipes for macOS, Ubuntu, Debian, CentOS, Docker][pgai-plpython].

      _macOS_: the standard PostgreSQL brew in Homebrew does not include the `plpython3` extension. These instructions show
      how to install from an alternate tap.

     - **[Postgresql plugin][asdf-postgres] for the [asdf][asdf] version manager**: set the `--with-python` option
       when installing PostgreSQL:

       ```bash
       POSTGRES_EXTRA_CONFIGURE_OPTIONS=--with-python asdf install postgres 16.3
       ```

   - **pgvector**: follow the [install instructions][pgvector-install] from the official repository.

   These extensions are automatically added to your PostgreSQL database when you
   [Enable the pgai extension](#enable-the-pgai-extension-in-your-database).

1. Make this `pgai` extension:

    ```bash
    make install
    ```
1. [Enable the pgai extension](#enable-the-pgai-extension-in-your-database).

### Enable the pgai extension in your database

1. Connect to your database with a postgres client like [psql v16](https://docs.timescale.com/use-timescale/latest/integrations/query-admin/psql/)
   or [PopSQL](https://docs.timescale.com/use-timescale/latest/popsql/).
   ```bash
   psql -d "postgres://<username>:<password>@<host>:<port>/<database-name>"
   ```

3. Create the pgai extension:

    ```sql
    CREATE EXTENSION IF NOT EXISTS ai CASCADE;
    ```

   The `CASCADE` automatically installs `pgvector` and `plpython3u` extensions.

### Use pgai

Now, use pgai to integrate AI from [Ollama](./docs/ollama.md) and [OpenAI](./docs/openai.md).
Learn how to [moderate](./docs/moderate.md) and [embed](./docs/delayed_embed.md)
content directly in the database using triggers and background jobs.

## Get involved

pgai is still at an early stage. Now is a great time to help shape the direction of this project;
we are currently deciding priorities. Have a look at the [list of features](https://github.com/timescale/pgai/issues) we're thinking of working on.
Feel free to comment, expand the list, or hop on the Discussions forum.

To get started, take a look at [how to contribute](./CONTRIBUTING.md)
and [how to set up a dev/test environment](./DEVELOPMENT.md).

## About Timescale

Timescale is a PostgreSQL database company. To learn more visit the [timescale.com](https://www.timescale.com).

Timescale Cloud is a high-performance, developer focused, cloud platform that provides PostgreSQL services
for the most demanding AI, time-series, analytics, and event workloads. Timescale Cloud is ideal for production applications and provides high availability, streaming backups, upgrades over time, roles and permissions, and great security.

[pgai-plpython]: https://github.com/postgres-ai/postgres-howtos/blob/main/0047_how_to_install_postgres_16_with_plpython3u.md
[asdf-postgres]: https://github.com/smashedtoatoms/asdf-postgres
[asdf]: https://github.com/asdf-vm/asdf
[python3]: https://www.python.org/downloads/
[pip]: https://pip.pypa.io/en/stable/installation/#supported-methods
[plpython3u]: https://www.postgresql.org/docs/current/plpython.html
[pgvector]: https://github.com/pgvector/pgvector
[pgvector-install]: https://github.com/pgvector/pgvector?tab=readme-ov-file#installation
[python-virtual-environment]: https://packaging.python.org/en/latest/tutorials/installing-packages/#creating-and-using-virtual-environments
[create-a-new-service]: https://console.cloud.timescale.com/dashboard/create_services
