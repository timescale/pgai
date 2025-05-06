"""Semantic Catalog module for managing database metadata and descriptions.

This module provides the core functionality for creating, managing, and interacting with
semantic catalogs. A semantic catalog stores metadata about database objects (tables,
views, procedures, etc.) along with natural language descriptions and vector embeddings
for semantic search capabilities.

The semantic catalog enables natural language queries about database schema, generating
SQL based on natural language prompts, and managing database documentation.
"""

import logging
from collections.abc import Sequence
from typing import Any, TextIO

import psycopg
from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable, Identifier
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
from pgai.semantic_catalog.gen_sql import ContextMode, GenerateSQLResponse
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
    """Represents a semantic catalog in the database.
    
    A semantic catalog is a collection of database object metadata, descriptions,
    and vector embeddings that enable semantic search capabilities and natural
    language interactions with the database schema.
    
    Attributes:
        id: The unique identifier of the semantic catalog.
        name: The name of the semantic catalog.
    """
    
    def __init__(self, id: int, name: str):
        """Initialize a SemanticCatalog instance.
        
        Args:
            id: The unique identifier of the semantic catalog.
            name: The name of the semantic catalog.
        """
        self._id = id
        self._name = name

    @property
    def id(self) -> int:
        """Get the unique identifier of the semantic catalog.
        
        Returns:
            The semantic catalog ID.
        """
        return self._id

    @property
    def name(self) -> str:
        """Get the name of the semantic catalog.
        
        Returns:
            The semantic catalog name.
        """
        return self._name

    async def drop(self, con: CatalogConnection) -> None:
        """Drop the semantic catalog from the database.
        
        Deletes the semantic catalog and all its associated data from the database.
        
        Args:
            con: The database connection to the catalog database.
        """
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
        """Add an embedding configuration to the semantic catalog.
        
        Creates a new embedding configuration in the semantic catalog. If an embedding name
        is not provided, a default name will be generated.
        
        Args:
            con: The database connection to the catalog database.
            config: The embedding configuration to add.
            embedding_name: Optional name for the embedding. If not provided, a default
                name will be generated.
                
        Returns:
            A tuple containing the embedding name and the embedding configuration that was added.
            
        Raises:
            RuntimeError: If the embedding could not be added.
        """
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
        """Drop an embedding configuration from the semantic catalog.
        
        Removes an embedding configuration and all its associated embeddings from the
        semantic catalog.
        
        Args:
            con: The database connection to the catalog database.
            embedding_name: Name of the embedding configuration to drop.
        """
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
        """List all embedding configurations in the semantic catalog.
        
        Retrieves all embedding configurations defined in the semantic catalog.
        
        Args:
            con: The database connection to the catalog database.
            
        Returns:
            A list of tuples, each containing an embedding name and its configuration.
        """
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
        """Get a specific embedding configuration from the semantic catalog.
        
        Retrieves a single embedding configuration by name.
        
        Args:
            con: The database connection to the catalog database.
            embedding_name: Name of the embedding configuration to retrieve.
            
        Returns:
            The embedding configuration if found, None otherwise.
        """
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
        """Generate vector embeddings for items in the semantic catalog.
        
        Processes all database objects, SQL examples, and facts in the semantic catalog
        that don't yet have embeddings for the specified embedding configuration.
        
        Args:
            con: The database connection to the catalog database.
            embedding_name: Name of the embedding configuration to use.
            config: The embedding configuration to use.
            batch_size: Number of items to process in each batch.
        """
        logger.debug(
            f"vectorizing embedding config {embedding_name} in semantic catalog {self.name}"  # noqa
        )
        await vectorize(con, self.id, embedding_name, config, batch_size)

    async def vectorize_all(self, con: CatalogConnection, batch_size: int = 32):
        """Generate vector embeddings for all embedding configurations.
        
        Processes all database objects, SQL examples, and facts in the semantic catalog
        for all embedding configurations defined in the catalog.
        
        Args:
            con: The database connection to the catalog database.
            batch_size: Number of items to process in each batch.
        """
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
        """Search for database objects using semantic search.
        
        Performs a semantic search for database objects that match the query.
        The query can be a natural language string or a vector embedding.
        
        Args:
            con: The database connection to the catalog database.
            embedding_name: Name of the embedding configuration to use for the search.
            query: Natural language query string or vector embedding.
            limit: Maximum number of results to return.
            
        Returns:
            A list of ObjectDescription objects ordered by similarity to the query.
            
        Raises:
            RuntimeError: If the specified embedding configuration does not exist.
        """
        emb_cfg = await self.get_embedding(con, embedding_name)
        if emb_cfg is None:
            raise RuntimeError(f"No embedding named: {embedding_name}")
        if isinstance(query, str):
            logger.debug("vectorizing query")
            query = await vectorizer.vectorize_query(emb_cfg, query)
        return await search.search_objects(
            con, self.id, embedding_name, emb_cfg, query, limit
        )

    async def list_sql_examples(
        self,
        con: CatalogConnection,
    ) -> list[SQLExample]:
        """List all SQL examples in the semantic catalog.
        
        Retrieves all SQL examples stored in the semantic catalog.
        
        Args:
            con: The database connection to the catalog database.
            
        Returns:
            A list of SQLExample objects.
        """
        async with con.cursor(row_factory=dict_row) as cur:
            sql = SQL("""\
                select x.*
                from ai.{table} x
                order by x.id
            """).format(
                table=Identifier(f"semantic_catalog_sql_{self.id}"),
            )
            await cur.execute(sql)
            results: list[SQLExample] = []
            for row in await cur.fetchall():
                results.append(SQLExample(**row))
        return results

    async def search_sql_examples(
        self,
        con: CatalogConnection,
        embedding_name: str,
        query: str | Sequence[float],
        limit: int = 5,
    ) -> list[SQLExample]:
        """Search for SQL examples using semantic search.
        
        Performs a semantic search for SQL examples that match the query.
        The query can be a natural language string or a vector embedding.
        
        Args:
            con: The database connection to the catalog database.
            embedding_name: Name of the embedding configuration to use for the search.
            query: Natural language query string or vector embedding.
            limit: Maximum number of results to return.
            
        Returns:
            A list of SQLExample objects ordered by similarity to the query.
            
        Raises:
            RuntimeError: If the specified embedding configuration does not exist.
        """
        emb_cfg = await self.get_embedding(con, embedding_name)
        if emb_cfg is None:
            raise RuntimeError(f"No embedding named: {embedding_name}")
        if isinstance(query, str):
            logger.debug("vectorizing query")
            query = await vectorizer.vectorize_query(emb_cfg, query)
        return await search.search_sql_examples(
            con, self.id, embedding_name, emb_cfg, query, limit
        )

    async def list_facts(
        self,
        con: CatalogConnection,
    ) -> list[Fact]:
        """List all facts in the semantic catalog.
        
        Retrieves all facts stored in the semantic catalog.
        
        Args:
            con: The database connection to the catalog database.
            
        Returns:
            A list of Fact objects.
        """
        async with con.cursor(row_factory=dict_row) as cur:
            sql = SQL("""\
                select x.*
                from ai.{table} x
                order by x.id
            """).format(
                table=Identifier(f"semantic_catalog_fact_{self.id}"),
            )
            await cur.execute(sql)
            results: list[Fact] = []
            for row in await cur.fetchall():
                results.append(Fact(**row))
        return results

    async def search_facts(
        self,
        con: CatalogConnection,
        embedding_name: str,
        query: str | Sequence[float],
        limit: int = 5,
    ) -> list[Fact]:
        """Search for facts using semantic search.
        
        Performs a semantic search for facts that match the query.
        The query can be a natural language string or a vector embedding.
        
        Args:
            con: The database connection to the catalog database.
            embedding_name: Name of the embedding configuration to use for the search.
            query: Natural language query string or vector embedding.
            limit: Maximum number of results to return.
            
        Returns:
            A list of Fact objects ordered by similarity to the query.
            
        Raises:
            RuntimeError: If the specified embedding configuration does not exist.
        """
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
        """Load database objects based on their descriptions.
        
        Takes a list of object descriptions and loads the corresponding database objects
        (tables, views, procedures) with their metadata. If sample_size is greater than 0,
        it also retrieves sample data for tables and views.
        
        Args:
            con: The database connection to the target database.
            obj_desc: List of object descriptions to load.
            sample_size: Number of sample rows to retrieve from tables and views.
                If 0, no sample data is retrieved.
                
        Returns:
            A list of database objects (Tables, Views, Procedures) with metadata and descriptions.
        """
        return await loader.load_objects(con, obj_desc, sample_size)

    def render_objects(self, objects: list[Table | View | Procedure]) -> str:
        """Render database objects as SQL statements.
        
        Renders tables, views, and procedures as SQL statements that can be used to
        recreate them.
        
        Args:
            objects: List of database objects to render.
            
        Returns:
            A string containing the rendered SQL statements.
        """
        return render.render_objects(objects)

    def render_sql_examples(self, sql_examples: list[SQLExample]) -> str:
        """Render SQL examples as formatted text.
        
        Args:
            sql_examples: List of SQL examples to render.
            
        Returns:
            A string containing the rendered SQL examples.
        """
        return "\n\n".join(map(render.render_sql_example, sql_examples))

    def render_facts(self, facts: list[Fact]) -> str:
        """Render facts as formatted text.
        
        Args:
            facts: List of facts to render.
            
        Returns:
            A string containing the rendered facts.
        """
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
        iteration_limit: int = 5,
        context_mode: ContextMode = "semantic_search",
        obj_ids: list[int] | None = None,
        sql_ids: list[int] | None = None,
        fact_ids: list[int] | None = None,
    ) -> GenerateSQLResponse:
        """Generate a SQL statement based on a natural language prompt.
        
        Uses AI to generate a SQL statement that fulfills the user's request, based on
        context from the semantic catalog. The SQL is validated against the target database
        to ensure it's correct.
        
        Args:
            catalog_con: Connection to the semantic catalog database.
            target_con: Connection to the target database.
            model: AI model to use for generating SQL.
            prompt: Natural language prompt describing the desired SQL.
            usage: Optional usage tracking object.
            usage_limits: Optional usage limits.
            model_settings: Optional model settings.
            embedding_name: Name of the embedding to use for semantic search.
                If None, the first available embedding is used.
            sample_size: Number of sample rows to include in the context.
            iteration_limit: Maximum number of iterations for SQL refinement.
            context_mode: Mode for selecting context information ("semantic_search", "manual", etc.).
            obj_ids: Optional list of object IDs to include in the context (for "manual" mode).
            sql_ids: Optional list of SQL example IDs to include in the context (for "manual" mode).
            fact_ids: Optional list of fact IDs to include in the context (for "manual" mode).
            
        Returns:
            A GenerateSQLResponse object containing the generated SQL and other information.
            
        Raises:
            RuntimeError: If no embeddings are configured for the semantic catalog.
        """
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
            iteration_limit=iteration_limit,
            sample_size=sample_size,
            context_mode=context_mode,
            obj_ids=obj_ids,
            sql_ids=sql_ids,
            fact_ids=fact_ids,
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
        """Import catalog items from a YAML file into the semantic catalog.
        
        Reads catalog items (tables, views, procedures, SQL examples, facts) from a YAML file
        and imports them into the semantic catalog. After importing, it generates vector
        embeddings for the imported items using either all embedding configurations or
        a specific one.
        
        Args:
            catalog_con: Connection to the semantic catalog database.
            target_con: Connection to the target database.
            yaml: Text IO stream containing the YAML data to import.
            embedding_name: Optional name of the embedding configuration to use for vectorization.
                If None, all embedding configurations are used.
            batch_size: Number of items to process in each vectorization batch.
                If None, defaults to 32.
            console: Rich console for displaying progress information.
                If None, a default console is used.
                
        Raises:
            RuntimeError: If the specified embedding configuration is not found.
        """
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
        """Export the semantic catalog to a YAML file.
        
        Exports all catalog items (tables, views, procedures, SQL examples, facts) from
        the semantic catalog to a YAML file.
        
        Args:
            catalog_con: Connection to the semantic catalog database.
            yaml: Text IO stream to write the YAML data to.
        """
        await async_export_to_yaml(yaml, load_from_catalog(catalog_con, self.id))


async def from_id(con: CatalogConnection, id: int) -> SemanticCatalog:
    """Get a semantic catalog by its ID.
    
    Retrieves a semantic catalog from the database using its unique identifier.
    
    Args:
        con: Connection to the catalog database.
        id: The unique identifier of the semantic catalog to retrieve.
        
    Returns:
        A SemanticCatalog instance representing the semantic catalog.
        
    Raises:
        RuntimeError: If the semantic catalog is not installed or the specified ID is not found.
    """
    async with con.cursor(row_factory=dict_row) as cur:
        try:
            await cur.execute(
                """\
                select id, catalog_name
                from ai.semantic_catalog
                where id = %s
            """,
                (id,),
            )
        except psycopg.errors.UndefinedTable:
            raise RuntimeError(
                "Semantic catalog is not installed, please run: "
                + "pgai semantic-catalog create"
            ) from None
        row = await cur.fetchone()
        if row is None:
            raise RuntimeError(f"No semantic catalog found with id: {id}")
        return SemanticCatalog(row["id"], row["catalog_name"])


async def from_name(con: CatalogConnection, catalog_name: str) -> SemanticCatalog:
    """Get a semantic catalog by its name.
    
    Retrieves a semantic catalog from the database using its name.
    
    Args:
        con: Connection to the catalog database.
        catalog_name: The name of the semantic catalog to retrieve.
        
    Returns:
        A SemanticCatalog instance representing the semantic catalog.
        
    Raises:
        RuntimeError: If the semantic catalog is not installed or the specified name is not found.
    """
    async with con.cursor(row_factory=dict_row) as cur:
        try:
            await cur.execute(
                """\
                select id, catalog_name
                from ai.semantic_catalog
                where catalog_name = %s
            """,
                (catalog_name,),
            )
        except psycopg.errors.UndefinedTable:
            raise RuntimeError(
                "Semantic catalog is not installed, please run: "
                + "pgai semantic-catalog create"
            ) from None
        row = await cur.fetchone()
        if row is None:
            raise RuntimeError(
                f"No semantic catalog found with catalog_name: {catalog_name}"
            )
        return SemanticCatalog(row["id"], row["catalog_name"])


async def list_semantic_catalogs(con: CatalogConnection) -> list[SemanticCatalog]:
    """List all semantic catalogs in the database.
    
    Retrieves all semantic catalogs defined in the database.
    
    Args:
        con: Connection to the catalog database.
        
    Returns:
        A list of SemanticCatalog instances representing all semantic catalogs.
        
    Raises:
        RuntimeError: If the semantic catalog is not installed.
    """
    async with con.cursor(row_factory=dict_row) as cur:
        try:
            await cur.execute("""\
                select id, catalog_name
                from ai.semantic_catalog
            """)
        except psycopg.errors.UndefinedTable:
            raise RuntimeError(
                "Semantic catalog is not installed, please run: "
                + "pgai semantic-catalog create"
            ) from None
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
    """Create a new semantic catalog in the database.
    
    Creates a new semantic catalog with optional embedding configuration.
    
    Args:
        con: Connection to the catalog database.
        catalog_name: Optional name for the semantic catalog. If not provided,
            a default name will be generated.
        embedding_name: Optional name for the embedding configuration. If not provided,
            a default name will be generated.
        embedding_config: Optional embedding configuration to add to the semantic catalog.
            
    Returns:
        A SemanticCatalog instance representing the newly created semantic catalog.
        
    Raises:
        RuntimeError: If the semantic catalog could not be created.
    """
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
