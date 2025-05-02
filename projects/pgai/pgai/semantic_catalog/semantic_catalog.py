import logging
from collections.abc import Sequence
from typing import Any, TextIO

import psycopg
from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable
from pydantic_ai.models import KnownModelName, Model
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import Usage, UsageLimits
from rich.console import Console

from pgai.semantic_catalog import gen_sql, loader, render, search
from pgai.semantic_catalog.file import (
    async_export_to_yaml,
    import_from_yaml,
    load_from_catalog,
    save_to_catalog,
)
from pgai.semantic_catalog.gen_sql import GenerateSQLResponse
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
    vectorizer,
)

logger = logging.getLogger(__name__)
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
            logger.info(f"dropping semantic catalog {self.name}")
            await cur.execute(
                """\
                select ai.drop_semantic_catalog(%s)
            """,
                (self.name,),
            )

    async def add_embedding(
        self,
        con: CatalogConnection,
        config: EmbeddingConfig,
        embedding_name: str | None = None,
    ) -> tuple[str, EmbeddingConfig]:
        logger.debug(
            f"adding embedding config {embedding_name} to semantic catalog {self.name}"
        )
        async with con.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """\
                select x.embedding_name, x.config
                from ai.sc_add_embedding
                ( config=>%(config)s
                , catalog_name=>%(catalog_name)s
                , embedding_name=>%(embedding_name)s
                ) x
            """,
                {
                    "config": config.model_dump_json(),
                    "catalog_name": self.name,
                    "embedding_name": embedding_name,
                },
            )
            row = await cur.fetchone()
            if row is None:
                raise RuntimeError("Failed to add embedding")
            return str(row["embedding_name"]), embedding_config_from_dict(row["config"])

    async def drop_embedding(self, con: CatalogConnection, embedding_name: str):
        logger.debug(
            f"dropping embedding config {embedding_name} from semantic catalog {self.name}"  # noqa
        )
        async with con.cursor() as cur:
            await cur.execute(
                """\
                select ai.sc_drop_embedding
                ( embedding_name=>%(embedding_name)s
                , catalog_name=>%(catalog_name)s
                )
            """,
                {"embedding_name": embedding_name, "catalog_name": self.name},
            )

    async def list_embeddings(
        self, con: CatalogConnection
    ) -> list[tuple[str, EmbeddingConfig]]:
        results: list[tuple[str, EmbeddingConfig]] = []
        async with con.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """\
                select e.embedding_name, e.config
                from ai.semantic_catalog_embedding e
                where e.semantic_catalog_id = %s
                order by e.id
            """,
                (self._id,),
            )
            for row in await cur.fetchall():
                results.append(
                    (
                        str(row["embedding_name"]),
                        embedding_config_from_dict(row["config"]),
                    )
                )
        return results

    async def get_embedding(
        self, con: CatalogConnection, embedding_name: str
    ) -> EmbeddingConfig | None:
        async with con.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """\
                select e.config
                from ai.semantic_catalog_embedding e
                where e.semantic_catalog_id = %(catalog_id)s
                and e.embedding_name = %(embedding_name)s
            """,
                {"catalog_id": self._id, "embedding_name": embedding_name},
            )
            row = await cur.fetchone()
            return embedding_config_from_dict(row["config"]) if row else None

    async def vectorize(
        self,
        con: psycopg.AsyncConnection,
        embedding_name: str,
        config: EmbeddingConfig,
        batch_size: int = 32,
    ) -> None:
        logger.debug(
            f"vectorizing embedding config {embedding_name} in semantic catalog {self.name}"  # noqa
        )
        await vectorize(con, self.id, embedding_name, config, batch_size)

    async def vectorize_all(self, con: CatalogConnection, batch_size: int = 32):
        embeddings = await self.list_embeddings(con)
        for embedding_name, config in embeddings:
            await self.vectorize(con, embedding_name, config, batch_size)

    async def search_objects(
        self,
        con: CatalogConnection,
        embedding_name: str,
        query: str | Sequence[float],
        limit: int = 5,
    ) -> list[ObjectDescription]:
        emb_cfg = await self.get_embedding(con, embedding_name)
        if emb_cfg is None:
            raise RuntimeError(f"No embedding named: {embedding_name}")
        if isinstance(query, str):
            logger.debug("vectorizing query")
            query = await vectorizer.vectorize_query(emb_cfg, query)
        return await search.search_objects(
            con, self.id, embedding_name, emb_cfg, query, limit
        )

    async def search_sql_examples(
        self,
        con: CatalogConnection,
        embedding_name: str,
        query: str | Sequence[float],
        limit: int = 5,
    ) -> list[SQLExample]:
        emb_cfg = await self.get_embedding(con, embedding_name)
        if emb_cfg is None:
            raise RuntimeError(f"No embedding named: {embedding_name}")
        if isinstance(query, str):
            logger.debug("vectorizing query")
            query = await vectorizer.vectorize_query(emb_cfg, query)
        return await search.search_sql_examples(
            con, self.id, embedding_name, emb_cfg, query, limit
        )

    async def search_facts(
        self,
        con: CatalogConnection,
        embedding_name: str,
        query: str | Sequence[float],
        limit: int = 5,
    ) -> list[Fact]:
        emb_cfg = await self.get_embedding(con, embedding_name)
        if emb_cfg is None:
            raise RuntimeError(f"No embedding named: {embedding_name}")
        if isinstance(query, str):
            logger.debug("vectorizing query")
            query = await vectorizer.vectorize_query(emb_cfg, query)
        return await search.search_facts(
            con, self.id, embedding_name, emb_cfg, query, limit
        )

    async def load_objects(
        self,
        con: TargetConnection,
        obj_desc: list[ObjectDescription],
        sample_size: int = 0,
    ) -> list[Table | View | Procedure]:
        return await loader.load_objects(con, obj_desc, sample_size)

    def render_objects(self, objects: list[Table | View | Procedure]) -> str:
        return render.render_objects(objects)

    def render_sql_examples(self, sql_examples: list[SQLExample]) -> str:
        return "\n\n".join(map(render.render_sql_example, sql_examples))

    def render_facts(self, facts: list[Fact]) -> str:
        return "\n\n".join(map(render.render_fact, facts))

    async def generate_sql(
        self,
        catalog_con: psycopg.AsyncConnection,
        target_con: psycopg.AsyncConnection,
        model: KnownModelName | Model,
        prompt: str,
        usage: Usage | None = None,
        usage_limits: UsageLimits | None = None,
        model_settings: ModelSettings | None = None,
        embedding_name: str | None = None,
        sample_size: int = 3,
    ) -> GenerateSQLResponse:
        if embedding_name is None:
            embeddings = await self.list_embeddings(catalog_con)
            if not embeddings:
                raise RuntimeError("No embeddings configured for semantic catalog")
            embedding_name, emb_cfg = embeddings[0]
        else:
            emb_cfg = await self.get_embedding(catalog_con, embedding_name)
        assert emb_cfg is not None, "No embedding configured for semantic catalog"
        return await gen_sql.generate_sql(
            catalog_con,
            target_con,
            model,
            self.id,
            embedding_name,
            emb_cfg,
            prompt,
            usage=usage,
            usage_limits=usage_limits,
            model_settings=model_settings,
            sample_size=sample_size,
        )

    async def import_catalog(
        self,
        catalog_con: psycopg.AsyncConnection,
        target_con: psycopg.AsyncConnection,
        yaml: TextIO,
        embedding_name: str | None,
        batch_size: int | None = None,
        console: Console | None = None,
    ):
        batch_size = batch_size or 32
        console = console or Console(stderr=True, quiet=True)
        console.status("importing yaml file into semantic catalog...")
        await save_to_catalog(catalog_con, target_con, self.id, import_from_yaml(yaml))
        match embedding_name:
            case None:
                console.status("vectorizing all embedding configs...")
                await self.vectorize_all(catalog_con, batch_size)
            case _:
                console.status(f"finding '{embedding_name}' embedding config...")
                config = await self.get_embedding(catalog_con, embedding_name)
                if not config:
                    raise RuntimeError(f"embedding config '{embedding_name}' not found")
                console.status(f"vectorizing '{embedding_name}' embedding config...")
                await self.vectorize(catalog_con, embedding_name, config, batch_size)

    async def export_catalog(
        self,
        catalog_con: psycopg.AsyncConnection,
        yaml: TextIO,
    ):
        await async_export_to_yaml(yaml, load_from_catalog(catalog_con, self.id))


async def from_id(con: CatalogConnection, id: int) -> SemanticCatalog:
    async with con.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """\
            select id, catalog_name
            from ai.semantic_catalog
            where id = %s
        """,
            (id,),
        )
        row = await cur.fetchone()
        if row is None:
            raise RuntimeError(f"No semantic catalog found with id: {id}")
        return SemanticCatalog(row["id"], row["catalog_name"])


async def from_name(con: CatalogConnection, catalog_name: str) -> SemanticCatalog:
    async with con.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """\
            select id, catalog_name
            from ai.semantic_catalog
            where catalog_name = %s
        """,
            (catalog_name,),
        )
        row = await cur.fetchone()
        if row is None:
            raise RuntimeError(
                f"No semantic catalog found with catalog_name: {catalog_name}"
            )
        return SemanticCatalog(row["id"], row["catalog_name"])


async def list_semantic_catalogs(con: CatalogConnection) -> list[SemanticCatalog]:
    async with con.cursor(row_factory=dict_row) as cur:
        await cur.execute("""\
            select id, catalog_name
            from ai.semantic_catalog
        """)
        results: list[SemanticCatalog] = []
        for row in await cur.fetchall():
            results.append(SemanticCatalog(row["id"], row["catalog_name"]))
        return results


async def create(
    con: CatalogConnection,
    catalog_name: str | None = None,
    embedding_name: str | None = None,
    embedding_config: EmbeddingConfig | None = None,
) -> SemanticCatalog:
    async with con.cursor(row_factory=dict_row) as cur:
        params: list[Composable] = []
        args: dict[str, Any] = {}
        if catalog_name is not None:
            args["catalog_name"] = catalog_name
            params.append(SQL("catalog_name=>%(catalog_name)s"))
        if embedding_name is not None:
            args["embedding_name"] = embedding_name
            params.append(SQL("embedding_name=>%(embedding_name)s"))
        if embedding_config is not None:
            args["embedding_config"] = embedding_config.model_dump_json()
            params.append(SQL("embedding_config=>%(embedding_config)s"))
        sql = SQL("select ai.create_semantic_catalog({}) as id").format(
            SQL(", ").join(params)
        )
        await cur.execute(sql, args)
        row = await cur.fetchone()
        if row is None:
            raise RuntimeError("Failed to retrieve created semantic catalog")
        return await from_id(con, int(row["id"]))
