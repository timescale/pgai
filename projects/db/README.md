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

 
