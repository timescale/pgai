# dataclasses generation for CreateVectorizerParams
This module contains a script to generate dataclasses as params for the `CreateVectorizer` class.
If the interface for the extension is changed, running this script via uv run generate should update the dataclasses in configuration.py and vectorizer_params.py without needing to manually update them.

## How to use
The script itself queries the pg_catalog table of a database with pgai installed it has hardcoded all the parameter functions in generate.py to avoid creating dataclasses for functions that are not intended to be used as vectorizer parameters. This also means that this list has to be kept up to date.

To run the script first start a postgres database with pgai installed on port 5432 (e.g. the docker-compose in this folder) and then run the following command:
```bash
uv run generate
```