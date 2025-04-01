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

### testing
--extension tests
just docker-build
just docker-run
just docker-shell

//inside shell 1
just test-server

//inside shell 2
just build && just install-all
just test

--db tests 
just docker-build
just docker-run
just docker-shell

//inside shell 1
uv pip install fastapi[standard]
cd db && just test-server

//inside shell 2
uv sync --active
cd ../extension && just build && just install && cd ../pgai/db
just test