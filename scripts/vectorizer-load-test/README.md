# vectorizer load test

This repo contains scripts for load testing vectorizer with a large dataset.


We will use this dataset: https://huggingface.co/datasets/Cohere/wikipedia-22-12

The dataset is already chunked. We will load the dataset into one table and then
"de-chunk" it into a second table. This second table can be used for vectorizer
load tests. There are 8.59M rows in the original dataset.

## 1. Preparing the environment
In strict order, follow:

1. Add a `.env` file and put a `DB_URL` in it. The value should be a Postgres DB connection URL. It can be a local DB or a remote DB.
2. Run `./0_init.sh`. This will install and set up all dependencies required for running this project.

## 2. Generating a Vectorizer and its dataset
In order to generate a vectorizer, we first need to prepare its dataset from where the embeddings will be created.

In strict order, follow:

1. Run `source venv/bin/activate`. This will activate the Python virtual env in which dependencies have been installed.
2. Run `python3 1_load.py`. This will dump all the dataset into a new table called `wiki_orig`. As the dataset is pretty large, feel free to cancel the script at any moment in case you want a smaller dataset.
3. Run `./2_execute_sql.sh sql/1_prepare.sql`. This will create a new table called `wiki`, populated from `wiki_orig`. It is a dechunked version of `wiki_orig`, and will become the source table for the embeddings work.
4. (optional) run `./utils/dump_db.sh`. This will create a dump of your DB. In case you wanna run several tests, you can use it later in order to restore the initial status. Use `./utils/restore_db.sh` to restore it at any point.
5. run `./2_execute_sql.sh sql/2_test.sql`. This will trigger (not executing) the whole embeddings pipeline. Internally it does several stuff:
    - Installs [pgai](https://github.com/timescale/pgai) extension.
    - Installs [timescaledb](https://github.com/timescale/timescaledb) extension.
    - It sets the URL to the executor URL and its path. Generally, this is the full URL to the events path in [Bastion Gateway](https://github.com/timescale/savannah-bastion).
    - It creates a **vectorizer** with all it's configuration. Feel free to modify it as you wish right directly in the file.
    - It prints out several useful info such as:
      - Prints the recently created vectorizer row.
      - Prints the background job, who is in charge of checking if there are pending items in the queue.
      - Prints how many pending items in the queue. This number should go to zero after completing all the work.
    - Then it sends a request to the executor (remember, [Bastion Gateway](https://github.com/timescale/savannah-bastion) by default) so it enqueues a new invocation event, so the SF reads it and executes https://github.com/timescale/lambda-pg-vectorizer. Please see the whole flow if you want to know more [here](https://timescale.slab.com/posts/timescale-ai-embeddings-lambda-backend-e8fdtjim#h9bau-update-embeddings). 
    - Finally it keeps printing the queue forever so you can track the progress of the embeddings work.

    You can modify the URL of the executor and its path by setting the following env vars:
    - `EXECUTOR_URL`
    - `EXECUTOR_EVENTS_PATH`

    Additionally, you can disable the executor by setting the `EXECUTOR_DISABLED=true` env var. This is useful if you are pointing to a local database, and/or additionally to manually run the lambda locally later.

    In the case you want to skip the executor call, for example when running the lambda locally, you should comment the `select ai.execute_vectorizer(:vectorizer_id);` line.

