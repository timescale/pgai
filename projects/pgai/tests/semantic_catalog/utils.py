import json
import time
from functools import cached_property
from pathlib import Path
from typing import Any

import docker
import psycopg
from docker import DockerClient
from docker.models.containers import Container
from docker.models.images import Image
from docker.types import Mount
from psycopg.sql import SQL, Identifier

from pgai.semantic_catalog import describe, loader
from pgai.semantic_catalog.models import Procedure, Table, View

CONTAINER_NAME = "pgai-semantic-catalog"


class PostgresContainer:
    def __init__(self, container: Container):
        self._container = container

    @property
    def container(self) -> Container:
        return self._container

    @property
    def name(self) -> str | None:
        return self.container.name

    @cached_property
    def host(self) -> str:
        return self._container.ports["5432/tcp"][0]["HostIp"]

    @cached_property
    def port(self) -> str:
        return self._container.ports["5432/tcp"][0]["HostPort"]

    def connection_string(
        self, user: str = "postgres", database: str = "postgres"
    ) -> str:
        return f"postgres://{user}@{self.host}:{self.port}/{database}"

    def __str__(self):  # pyright: ignore [reportImplicitOverride]
        return self.connection_string()

    def wait_for(self):
        trigger = "database system is ready to accept connections"
        count = 0
        for line in self._container.logs(stream=True, follow=True):
            if trigger in line.decode("utf-8").strip():
                count = count + 1
                if count >= 2:
                    break

    def is_ready(
        self, timeout_seconds: float = 30.0, interval_seconds: float = 0.2
    ) -> bool:
        url = self.connection_string()
        start = time.time()
        while time.time() - start < timeout_seconds:
            try:
                with (
                    psycopg.connect(url, connect_timeout=1) as con,
                    con.cursor() as cur,
                ):
                    cur.execute("select 1")
                    cur.fetchall()
                return True
            except psycopg.OperationalError as _:
                time.sleep(interval_seconds)
        return False

    def drop_database(self, database_name: str, force: bool = True) -> None:
        with (
            psycopg.connect(self.connection_string(), autocommit=True) as con,
            con.cursor() as cur,
        ):
            query = SQL("drop database if exists {}").format(Identifier(database_name))
            if force:
                query = query + SQL(" with (force)")
            cur.execute(query)

    def create_database(self, database_name: str, owner: str | None = None) -> None:
        with (
            psycopg.connect(self.connection_string(), autocommit=True) as con,
            con.cursor() as cur,
        ):
            query = SQL("create database {}").format(Identifier(database_name))
            if owner is not None:
                query = query + SQL("owner={}").format(Identifier(owner))
            cur.execute(query)

    def drop_user(self, user_name: str) -> None:
        with psycopg.connect(self.connection_string()) as con, con.cursor() as cur:
            query = SQL("drop user if exists {}").format(Identifier(user_name))
            cur.execute(query)

    def create_user(self, user_name: str) -> None:
        with psycopg.connect(self.connection_string()) as con, con.cursor() as cur:
            query = SQL("create user {}").format(Identifier(user_name))
            cur.execute(query)

    @staticmethod
    def get(container_name: str = CONTAINER_NAME) -> "PostgresContainer | None":
        client: DockerClient = docker.from_env()
        containers: list[Container] = client.containers.list(  # pyright: ignore [reportUnknownVariableType, reportUnknownMemberType]
            filters={"name": container_name},
            all=True,
        )
        if not containers:
            return None
        return PostgresContainer(container=containers[0])  # pyright: ignore [reportUnknownVariableType, reportUnknownArgumentType]

    @staticmethod
    def get_or_create(
        container_name: str = CONTAINER_NAME,
        port: int = 5678,
        mounts: list[Mount] | None = None,
    ) -> "PostgresContainer":
        client: DockerClient = docker.from_env()
        maybe: PostgresContainer | None = PostgresContainer.get(container_name)
        if maybe is None:
            dockerfile = Path(__file__).parent.parent.parent.parent.joinpath(
                "extension"
            )
            image: Image = client.images.build(
                path=str(dockerfile), target="pgai-test-db"
            )[0]
            container = PostgresContainer(  # pyright: ignore [reportCallIssue, reportUnknownArgumentType]
                container=client.containers.run(  # pyright: ignore [reportCallIssue, reportUnknownArgumentType]
                    image=image.id,  # pyright: ignore [reportArgumentType]
                    name=container_name,
                    detach=True,
                    ports={"5432/tcp": ("127.0.0.1", port)},
                    environment={
                        "POSTGRES_HOST_AUTH_METHOD": "trust",
                        "POSTGRES_INITDB_ARGS": " ".join(
                            [
                                "-c shared_preload_libraries='timescaledb, pgextwlist'",
                                "-c extwlist.extensions='ai,vector'",
                            ]
                        ),
                    },
                    mounts=mounts,
                )
            )
            container.wait_for()
        else:
            container: PostgresContainer = maybe
            if container.container.status != "running":
                container.container.start()
                container.wait_for()
        assert container is not None
        while "5432/tcp" not in container.container.ports:
            time.sleep(0.1)
            maybe = PostgresContainer.get(container_name)
            if maybe is None:
                raise RuntimeError(f"Could not find container {container_name}")
            container = maybe
        assert container is not None
        if not container.is_ready():
            raise RuntimeError("Postgres container not ready.")
        return container


async def gen_tables_json(container: PostgresContainer):
    stuff = {}
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database="postgres_air")
    ) as con:
        oids = await describe.find_tables(con)
        tables = await loader.load_tables(con, oids)
        for table in tables:
            stuff[table.table_name] = table.model_dump()
    Path(__file__).parent.joinpath("data", "tables.json").write_text(
        json.dumps(stuff, indent=2)
    )


async def gen_views_json(container: PostgresContainer):
    stuff = {}
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database="postgres_air")
    ) as con:
        oids = await describe.find_views(con)
        views = await loader.load_views(con, oids)
        for view in views:
            stuff[view.view_name] = view.model_dump()
    Path(__file__).parent.joinpath("data", "views.json").write_text(
        json.dumps(stuff, indent=2)
    )


async def gen_procs_json(container: PostgresContainer):
    stuff = {}
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database="postgres_air")
    ) as con:
        oids = await describe.find_procedures(con)
        procs = await loader.load_procedures(con, oids)
        for proc in procs:
            stuff[proc.proc_name] = proc.model_dump()
    Path(__file__).parent.joinpath("data", "procedures.json").write_text(
        json.dumps(stuff, indent=2)
    )


def get_table_dict() -> dict[str, Table]:
    raw: dict[str, Any] = json.loads(
        Path(__file__).parent.joinpath("data", "tables.json").read_text()
    )
    return {k: Table(**v) for k, v in raw.items()}


def get_tables() -> list[Table]:
    d = get_table_dict()
    keys = [k for k in d]
    keys.sort()
    vals: list[Table] = []
    for k in keys:
        val = d[k]
        vals.append(val)
    return vals


def get_view_dict() -> dict[str, View]:
    raw: dict[str, Any] = json.loads(
        Path(__file__).parent.joinpath("data", "views.json").read_text()
    )
    return {k: View(**v) for k, v in raw.items()}


def get_views() -> list[View]:
    d = get_view_dict()
    keys = [k for k in d]
    keys.sort()
    vals: list[View] = []
    for k in keys:
        val = d[k]
        vals.append(val)
    return vals


def get_procedure_dict() -> dict[str, Procedure]:
    raw: dict[str, Any] = json.loads(
        Path(__file__).parent.joinpath("data", "procedures.json").read_text()
    )
    return {k: Procedure(**v) for k, v in raw.items()}


def get_procedures() -> list[Procedure]:
    d = get_procedure_dict()
    keys = [k for k in d]
    keys.sort()
    vals: list[Procedure] = []
    for k in keys:
        val = d[k]
        vals.append(val)
    return vals


async def load_airports(con: psycopg.AsyncConnection) -> None:
    airport_data = Path(__file__).parent.joinpath("data", "airport.sql").read_text()
    async with (
        con.cursor() as cur,
        cur.copy("copy postgres_air.airport from stdin with (format csv)") as cpy,
    ):
        await cpy.write(airport_data)
