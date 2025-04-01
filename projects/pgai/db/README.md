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
just docker-build docker-run
docker exec pgai-ext just build install-all
docker exec -d pgai-ext just test-server
just docker-shell

//inside shell 
just test
// or `uv run --no-project pytest -x` or similar 

--db tests 
just docker-build docker-run docker-sync
docker exec pgai-db just build
docker exec -d pgai-db just test-server
just docker-shell
 
//inside shell
just test