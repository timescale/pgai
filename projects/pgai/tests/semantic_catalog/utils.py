import time
from pathlib import Path
from functools import cached_property

import docker
import psycopg
from docker.models.containers import Container

CONTAINER_NAME = "pgai-semantic-catalog"


class PostgresContainer:
    def __init__(self, container: Container):
        self._container = container

    @property
    def container(self) -> Container:
        return self._container

    @cached_property
    def host(self) -> str:
        return self._container.ports["5432/tcp"][0]["HostIp"]

    @cached_property
    def port(self) -> str:
        return self._container.ports["5432/tcp"][0]["HostPort"]

    def connection_string(self, user: str = "postgres", database: str = "postgres") -> str:
        return f"postgres://{user}@{self.host}:{self.port}/{database}"

    def __str__(self):
        return self.connection_string()

    def wait_for(self):
        trigger = "database system is ready to accept connections"
        count = 0
        for line in self._container.logs(stream=True, follow=True):
            if trigger in line.decode('utf-8').strip():
                count = count + 1
                if count >= 2:
                    break

    def is_ready(self, timeout_seconds: float = 30.0, interval_seconds: float = 0.2) -> bool:
        url = self.connection_string()
        start = time.time()
        while time.time() - start < timeout_seconds:
            try:
                with psycopg.connect(url, connect_timeout=1) as con:
                    with con.cursor() as cur:
                        cur.execute("select 1")
                        cur.fetchall()
                    return True
            except psycopg.OperationalError as _:
                time.sleep(interval_seconds)
        return False

    def drop_database(self, database_name: str, force: bool = True) -> None:
        with psycopg.connect(self.connection_string(), autocommit=True) as con:
            with con.cursor() as cur:
                cur.execute(f"drop database if exists {database_name}{' with (force)' if force else ''}")

    def create_database(self, database_name: str, owner: str | None = None) -> None:
        with psycopg.connect(self.connection_string(), autocommit=True) as con:
            with con.cursor() as cur:
                cur.execute(f"create database {database_name}{f' owner={owner}' if owner else ''}")

    def drop_user(self, user_name: str) -> None:
        with psycopg.connect(self.connection_string()) as con:
            with con.cursor() as cur:
                cur.execute(f"drop user if exists {user_name}")

    def create_user(self, user_name: str) -> None:
        with psycopg.connect(self.connection_string()) as con:
            with con.cursor() as cur:
                cur.execute(f"create user {user_name}")

    @staticmethod
    def get(container_name: str = CONTAINER_NAME):
        client = docker.from_env()
        containers: list[Container] = client.containers.list(filters={"name": container_name})
        if containers and len(containers) > 0:
            return PostgresContainer(containers[0])
        return None

    @staticmethod
    def get_or_create(container_name: str = CONTAINER_NAME, port: int = 5678):
        client = docker.from_env()
        container = PostgresContainer.get(container_name)
        if container is None:
            dockerfile = Path(__file__).parent.parent.parent.parent.joinpath("extension")
            image, _ = client.images.build(path=str(dockerfile), target="pgai-test-db")
            container = PostgresContainer(client.containers.run(
                image=image.id,
                name=container_name,
                detach=True,
                ports={"5432/tcp": ('127.0.0.1', port)},
                environment={
                    "POSTGRES_HOST_AUTH_METHOD": "trust",
                    "POSTGRES_INITDB_ARGS": " ".join([
                        "-c shared_preload_libraries='timescaledb, pgextwlist'",
                        "-c extwlist.extensions='ai,vector'"
                    ])
                }
            ))
            container.wait_for()
        while "5432/tcp" not in container.container.ports:
            time.sleep(0.1)
            container = PostgresContainer.get(container_name)
        assert container is not None
        if not container.is_ready():
            raise RuntimeError("Postgres container not ready.")
        return container

