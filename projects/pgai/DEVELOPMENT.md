## Working on the pgai library

The experience of working on the pgai library is like developing most Python
libraries and applications. We use [uv](https://docs.astral.sh/uv/getting-started/installation/) to manage dependencies and python versions. Once you have uv installed it's easy to get started.

Note: We try to somewhat follow the python release schedule for supported versions to allow more users to use our library.
Therefore we are about a year behind the latest python release.

Uv syncs the dependencies of all developers working on the project via the uv.lock file. If you want to add a new dependency make use of the uv add command:

```bash
uv add --directory projects/pgai <package-name>
```

If it is a development dependency and not needed at runtime, you can add the --dev flag:

```bash
uv add --directory projects/pgai --dev <package-name>
```

Uv installs all dependencies inside a virtual environment by default you can either activate this via the `uv shell` command or run commands directly via `uv run`.

For the most common commands use the just recipes.

```bash
just -l pgai
```

Be sure to add unit tests to the [tests](./projects/pgai/tests) directory when
you add or modify code. Use the following commands to check your work before
submitting a PR.

```bash
just pgai test
just pgai lint
just pgai format
just pgai type-check
```

## Making sure concurrency is working correctly

Making sure concurrency is working correctly is a bit tricky and manual for now. An easy way to see if concurrency is working is to run the following command:

```bash
uv run pytest -k test_process_vectorizer\[4 -rP
```

This will run the openai test with concurrency and print the output to the console. Then you have to verify the logs look interleaved between the two workers.
