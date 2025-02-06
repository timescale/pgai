# Install pgai with Docker

To run pgai, you need to run two containers:

1. A PostgreSQL instance with the pgai extension installed.
2. A vectorizer worker that syncs your data to the database and creates embeddings (only needed if using pgai vectorizer) .

We have example docker-compose files to get you started:

- [docker compose for pgai](/examples/docker_compose_pgai_ollama/docker-compose.yml) - for using pgai with OpenAI and Voyage AI
- [docker compose for pgai with Ollama](/examples/docker_compose_pgai_ollama/docker-compose.yml) - for using pgai with Ollama running locally

If you want to run the containers by themselves, see the detailed instructions below.

## Detailed instructions for running the containers 

### Run the PostgreSQL instance

1. Run the docker container. The suggested command is:
   ```
   docker run -d --name pgai -p 5432:5432 \
   -v pg-data:/home/postgres/pgdata/data \
   -e POSTGRES_PASSWORD=password timescale/timescaledb-ha:pg17
   ``` 

   This will start a PostgreSQL instance for development purposes using a volume called `pg-data` for data storage. To run in production, you would need to change the password above. See the full  [Docker image instructions](https://docs.timescale.com/self-hosted/latest/install/installation-docker/) for more information. You'll be able to connect to the database using the following connection string: `postgres://postgres:password@localhost/postgres`

2. Create the pgai extension in your database:

    ```
    docker exec -it pgai psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS ai CASCADE;"
    ```

### Run the vectorizer worker

1. Run the [vectorizer worker](https://hub.docker.com/r/timescale/pgai-vectorizer-worker) container:

    ```
    docker run -d --name pgai-vectorizer-worker -e PGAI_VECTORIZER_WORKER_DB_URL=postgres://postgres:password@localhost/postgres timescale/pgai-vectorizer-worker:latest
    ```
