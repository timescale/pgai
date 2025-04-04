from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable

from pgai.semantic_catalog import loader, render, search
from pgai.semantic_catalog.models import (
    Fact,
    ObjectDescription,
    Procedure,
    SQLExample,
    Table,
    View,
)
from pgai.semantic_catalog.vectorizer import (
    EmbeddingConfig,
    embedding_config_from_dict,
    vectorize,
)

TargetConnection = psycopg.AsyncConnection
CatalogConnection = psycopg.AsyncConnection


class SemanticCatalog:
    def __init__(self, id: int, name: str):
        self._id = id
        self._name = name

    @property
    def id(self) -> int:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    async def drop(self, con: CatalogConnection) -> None:
        async with con.cursor() as cur:
            await cur.execute(
                """\
                select ai.drop_semantic_catalog(%s)
            """,
                (self.name,),
            )

    async def add_embedding_config(
        self, con: CatalogConnection, config: EmbeddingConfig
    ) -> str | None:
        async with con.cursor() as cur:
            await cur.execute(
                """\
                select ai.sc_add_embedding_config(%s, %s)
            """,
                (config.model_dump_json(), self.name),
            )
            row = await cur.fetchone()
            return str(row[0]) if row else None

    async def drop_embedding_config(self, con: CatalogConnection, name: str):
        async with con.cursor() as cur:
            await cur.execute(
                """\
                select ai.sc_drop_embedding_config(%s, %s)
            """,
                (name, self.name),
            )

    async def get_embedding_configs(
        self, con: CatalogConnection
    ) -> dict[str, EmbeddingConfig]:
        results: dict[str, EmbeddingConfig] = {}
        async with con.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """\
                select x.key, x.value
                from ai.semantic_catalog c
                cross join lateral jsonb_each(c.config->'embeddings') x
                where c.id = %s
            """,
                (self._id,),
            )
            for row in await cur.fetchall():
                results[str(row["key"])] = embedding_config_from_dict(row["value"])
        return results

    async def get_embedding_config(
        self, con: CatalogConnection, name: str
    ) -> EmbeddingConfig | None:
        async with con.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """\
                select x.key, x.value
                from ai.semantic_catalog c
                cross join lateral jsonb_each(c.config->'embeddings') x
                where c.id = %s
                and x.key = %s
            """,
                (self._id, name),
            )
            row = await cur.fetchone()
            return embedding_config_from_dict(row["value"]) if row else None

    async def vectorize(
        self,
        con: psycopg.AsyncConnection,
        name: str,
        config: EmbeddingConfig,
        batch_size: int | None = 32,
    ) -> None:
        await vectorize(con, self.id, name, config, batch_size if batch_size else 32)

    async def vectorize_all(self, con: CatalogConnection, batch_size: int | None = 32):
        configs = await self.get_embedding_configs(con)
        for name, config in configs.items():
            await self.vectorize(con, name, config, batch_size)

    async def search_objects(
        self, con: CatalogConnection, emb_name: str, query: str, limit: int = 5
    ) -> list[ObjectDescription]:
        emb_cfg = await self.get_embedding_config(con, emb_name)
        if emb_cfg is None:
            raise RuntimeError(f"No embedding config for {emb_name}")
        return await search.search_objects(
            con, self.id, emb_name, emb_cfg, query, limit
        )

    async def search_sql_examples(
        self, con: CatalogConnection, emb_name: str, query: str, limit: int = 5
    ) -> list[SQLExample]:
        emb_cfg = await self.get_embedding_config(con, emb_name)
        if emb_cfg is None:
            raise RuntimeError(f"No embedding config for {emb_name}")
        return await search.search_sql_examples(
            con, self.id, emb_name, emb_cfg, query, limit
        )

    async def search_facts(
        self, con: CatalogConnection, emb_name: str, query: str, limit: int = 5
    ) -> list[Fact]:
        emb_cfg = await self.get_embedding_config(con, emb_name)
        if emb_cfg is None:
            raise RuntimeError(f"No embedding config for {emb_name}")
        return await search.search_facts(con, self.id, emb_name, emb_cfg, query, limit)

    async def load_objects(
        self, con: TargetConnection, obj_desc: list[ObjectDescription]
    ) -> list[Table | View | Procedure]:
        return await loader.load_objects(con, obj_desc)

    def render_objects(self, objects: list[Table | View | Procedure]) -> str:
        return render.render_objects(objects)

    async def render_sql_examples(self, sql_examples: list[SQLExample]) -> str:
        return "\n\n".join(map(render.render_sql_example, sql_examples))

    async def render_facts(self, facts: list[Fact]) -> str:
        return "\n\n".join(map(render.render_fact, facts))


async def from_id(con: CatalogConnection, id: int) -> SemanticCatalog:
    async with con.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """\
            select id, name
            from ai.semantic_catalog
            where id = %s
        """,
            (id,),
        )
        row = await cur.fetchone()
        if row is None:
            raise ValueError(f"No semantic catalog found with id {id}")
        return SemanticCatalog(row["id"], row["name"])


async def from_name(con: CatalogConnection, name: str) -> SemanticCatalog:
    async with con.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """\
            select id, name
            from ai.semantic_catalog
            where name = %s
        """,
            (name,),
        )
        row = await cur.fetchone()
        if row is None:
            raise ValueError(f"No semantic catalog found with name {name}")
        return SemanticCatalog(row["id"], row["name"])


async def create_semantic_catalog(
    con: CatalogConnection,
    name: str | None = None,
    config: EmbeddingConfig | None = None,
) -> SemanticCatalog:
    async with con.cursor(row_factory=dict_row) as cur:
        params: list[Composable] = []
        args: dict[str, Any] = {}
        if name is not None:
            args["name"] = name
            params.append(SQL("catalog_name=%(name)s"))
        if config is not None:
            args["config"] = config
            params.append(SQL("embedding=%(config)s"))
        sql = SQL("select ai.create_semantic_catalog({}) as id").format(
            SQL(", ").join(params)
        )
        await cur.execute(sql, args)
        row = await cur.fetchone()
        if row is None:
            raise ValueError("Failed to retrieve created semantic catalog")
        return await from_id(con, int(row["id"]))
