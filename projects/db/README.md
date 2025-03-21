# notes on the changes

- vectorizer job
-> leaving ai.execute_vectorizer in extension
->  ai._vectorizer_job which calls ai.execute_vectorizer is moved to dbapp

-> creating the index still needs to be handled (probably through the worker)

- had to get rid of ai._vectorizer_handle_drops() and create event trigger _vectorizer_handle_drops
-> need to add a job that goes through vectorizers and checks for dropped tables
--> then calls perform ai.drop_vectorizer(_id);


- had to get rid of _vectorizer_create_dependencies
-> no way to enforce CASCADE requirement on source drops


- weirdness with python package naming
- we have two packages:
    - projects/extension (named pgai but imports as ai) - we should rename this to something else?
    - projects/pgai (named pgai and imports as pgai) - (I think this is the one in PIP)

# todo

- should we `uv sync` in the dev container in /db?
- unpackage tests from all previous versions
- fix test_jill_privileges, create_vectorizer_privileges test


 
# dev notes
- ./build.py docker-start
- ./build.py docker-shell

## inside the container
- uv run pgai install 


### testing

- `uv venv --directory /py/`
- `export VIRTAUL_ENV=/py/.venv/`
- in the pgai directory, run `VIRTAUL_ENV=/py/.venv/ uv pip install --editable .`
- in the extension directory, run `just build && just install-all && uv run --no-project pytest -k unpackaged`

- in the db dir 
- `VIRTAUL_ENV=/py/.venv/ PATH=/py/.venv/bin/:$PATH uv pip install pytest`
- `uv pip install fastapi[standard]`


---
`uv venv --directory /py/`
`source /py/.venv/bin/activate`
`uv pip install pytest fastapi[standard]`
`just build && just install`
`uv sync --active`
`cd ../pgai && uv pip install --editable .`
