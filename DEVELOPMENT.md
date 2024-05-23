# Development

## "Building"

The pgai extension is written in SQL files with database functions written in
plpython3u. Conveniently, there is no compilation required.

Copy the extension sources to the appropriate postgres directory with the 
following command. (This assumes your current working directory is the root of 
this repo.)

```bash
cp ai* `pg_config --sharedir`/extension/
```

Next, create the extension with the new sources.

```sql
drop extension if exists ai;
create extension ai cascade;
```

## Testing

The `tests.sql` file contains unit tests. Add new tests for new functionality.

Run the tests with the following command:

```bash
psql -v OPENAI_API_KEY=$OPENAI_API_KEY -f tests.sql
```

Or if you already have a psql session going you can run the tests from psql 
with:

```sql
\i tests.sql
```

## Development with Docker

You may want to do your development and testing in a docker container.

### Building the image

```bash
docker build -t pgai .
```

### Running the container

This runs the container and bind mounts the working directory (this repo) to 
the /pgai directory in the container.

```bash
docker run -d --name pgai -p 9876:5432 -e POSTGRES_PASSWORD=pgaipass --mount type=bind,src=`pwd`,dst=/pgai pgai
```

### Getting a terminal in the container

```bash
docker exec -it pgai /bin/bash
```

### Connecting to the database

```bash
psql -d "postgres://postgres:pgaipass@localhost:9876/postgres"
```

### "Building" from outside the container

This command will copy the sources from the repo directory on the bind mount to
the appropriate postgres directory from outside the container.

```bash
docker exec pgai /bin/bash -c 'cp /pgai/ai* `pg_config --sharedir`/extension/'
```

## Development with a Virtual Machine

You may want to do your development and testing in a virtual machine.

The `vm.sh` shell script will create a virtual machine named `pgai` using 
[multipass](https://multipass.run/) for development use. The repo directory 
will be mounted to `/pgai` in the virtual machine.

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

