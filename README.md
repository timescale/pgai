# Postgres AI

Artificial intelligence for Postgres.

## Docker

### Building the image

```bash
docker build -t pgai .
```

### Running the container

```bash
docker run -d --name pgai -p 9876:5432 -e POSTGRES_PASSWORD=pgaipass pgai
```

### Connecting to the database

```bash
psql -d "postgres://postgres:pgaipass@localhost:9876/postgres"
```

### Creating the extension

```sql
CREATE EXTENSION ai CASCADE;
```

## Prerequisites

1. PostgreSQL (obviously) version 16
2. [plpython3u](https://www.postgresql.org/docs/current/plpython.html)
3. [pgvector](https://github.com/pgvector/pgvector)
4. Python3 with the following packages
    1. [openai](https://pypi.org/project/openai/)
    2. [tiktoken](https://pypi.org/project/tiktoken/)

## Installation

Using docker is recommended, however a Makefile is provided if you wish to 
install the extension on your system. The `install` make target will download 
and install the pgvector extension, install the pgai extension, and install 
the Python package dependencies in your system's Python environment.

```bash
make install
```

## Create Extension

After installation, the extension must be created in a Postgres database. Since
the extension depends on both plpython3u and pgvector, using the `CASCADE` 
option is recommended to automatically install them if they are not already.

```sql
CREATE EXTENSION IF NOT EXISTS ai CASCADE;
```

Alternately, you can use the `create_extension` make target. Be aware that the
`DB` and `USER` make variables are used to establish a connection to the 
running database, so modify them accordingly if needed.

```bash
make create_extension
```

## Development

The `vm.sh` shell script will create a virtual machine named `pgai` using 
[multipass](https://multipass.run/) for development use. The repo director will
be mounted to `/pgai` in the virtual machine.

### Create the virtual machine

```bash
./vm.sh
```

### Get a shell in the virtual machine

```bash
multipass shell pgai
```

### Delete the virtual machine

```bash
multipass delete --purge pgai
```