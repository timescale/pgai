## Working on the pgai library


Note: We try to somewhat follow the python release schedule for supported versions to allow more users to use our library.
Therefore, we are about a year behind the latest python release.

### Set up your environment

The experience of working on the pgai library is like developing most Python
libraries and applications. We use [uv](https://docs.astral.sh/uv/getting-started/installation/) to manage dependencies and python versions. Once you have uv installed it's easy to get started.

Make sure your uv version is at least `0.5.x`.

```bash
uv --version
```

If not, upgrade it with this command.

```bash
uv self update
```

Change directory into the [projects/pgai](/projects/pgai) directory and create a
virtual environment. Then, activate it.

```bash
cd projects/pgai
uv venv
source .venv/bin/activate
```

Install the project's dependencies into the virtual environment.

```bash
uv sync --all-extras
```

The vectorizer worker and some tests use environment variables and can make use
of a `.env` file. Creating one may make your life easier. Include the variables 
below as you see fit.

```text
OLLAMA_HOST=""
OPENAI_API_KEY=""
VOYAGE_API_KEY=""
MISTRAL_API_KEY=""
COHERE_API_KEY=""
HUGGINGFACE_API_KEY=""
AZURE_OPENAI_API_KEY=""
AZURE_OPENAI_API_BASE=""
AZURE_OPENAI_API_VERSION=""
ENABLE_VECTORIZER_TOOL_TESTS=1
```

Run the tests to verify you have a working environment.

```bash
just test
```

### Manage Python Dependencies

Uv syncs the dependencies of all developers working on the project via the uv.lock file. If you want to add a new dependency make use of the uv add command:

```bash
uv add --directory projects/pgai <package-name>
```

If it is a development dependency and not needed at runtime, you can add the --dev flag:

```bash
uv add --directory projects/pgai --dev <package-name>
```

### Working with the project

We use [just](https://just.systems/man/en/) to define and run commands to work
with the project. These include tasks like building, installation, linting, 
and running tests. To see a list of the available commands, run the following 
from the root of the repo:

```bash
just -l pgai
```

### Testing the pgai library

Be sure to add unit tests to the [tests](./projects/pgai/tests) directory when
you add or modify code. Use the following commands to check your work before
submitting a PR.

```bash
just pgai test
just pgai lint
just pgai format
just pgai type-check
```