import psycopg
import pytest
from psycopg.rows import dict_row

import pgai
import pgai.semantic_catalog as sc
from pgai.semantic_catalog.vectorizer import (
    OllamaConfig,
    OpenAIConfig,
    SentenceTransformersConfig,
)
from tests.semantic_catalog.utils import PostgresContainer

DATABASE = "sc_01"


@pytest.fixture(scope="module", autouse=True)
def database(container: PostgresContainer):
    container.drop_database(DATABASE, force=True)
    container.create_database(DATABASE)
    pgai.install(container.connection_string(database=DATABASE))


async def test_semantic_catalog(container: PostgresContainer):
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        # all defaults
        cat1 = await sc.create(con)
        assert cat1.name == "default"
        embs = await cat1.list_embeddings(con)
        assert len(embs) == 1
        emb_name, config = embs[0]
        assert emb_name == "emb1"
        assert isinstance(config, SentenceTransformersConfig)

        # add a second semantic catalog
        cat2 = await sc.create(con, catalog_name="cat2")
        assert cat2.name == "cat2"
        embs = await cat2.list_embeddings(con)
        assert len(embs) == 1
        emb_name, config = embs[0]
        assert emb_name == "emb1"
        assert isinstance(config, SentenceTransformersConfig)

        # add a third semantic catalog
        config = OllamaConfig.create(model="nomic-embed-text", dimensions=768)
        cat3 = await sc.create(
            con, catalog_name="cat3", embedding_name="vec1", embedding_config=config
        )
        assert cat3.name == "cat3"
        embs = await cat3.list_embeddings(con)
        assert len(embs) == 1
        emb_name, config = embs[0]
        assert emb_name == "vec1"
        assert isinstance(config, OllamaConfig)
        assert config.model == "nomic-embed-text"
        assert config.dimensions == 768

        # add a second embedding
        config = OpenAIConfig.create(model="text-embedding-ada-002", dimensions=1536)
        emb_name, config = await cat3.add_embedding(con, config)
        assert emb_name == "emb2"
        assert isinstance(config, OpenAIConfig)
        assert config.model == "text-embedding-ada-002"
        assert config.dimensions == 1536

        # add a third embedding
        config = SentenceTransformersConfig.create(
            model="nomic-ai/nomic-embed-text-v1.5", dimensions=768
        )
        emb_name, config = await cat3.add_embedding(con, config)
        assert emb_name == "emb3"
        assert isinstance(config, SentenceTransformersConfig)
        assert config.model == "nomic-ai/nomic-embed-text-v1.5"
        assert config.dimensions == 768

        # drop the second
        await cat3.drop_embedding(con, "emb2")
        embs = await cat3.list_embeddings(con)
        assert len(embs) == 2
        emb_name, config = embs[0]
        assert emb_name == "vec1"
        assert isinstance(config, OllamaConfig)
        assert config.model == "nomic-embed-text"
        assert config.dimensions == 768
        emb_name, config = embs[1]
        assert emb_name == "emb3"
        assert isinstance(config, SentenceTransformersConfig)
        assert config.model == "nomic-ai/nomic-embed-text-v1.5"
        assert config.dimensions == 768

        # add a fourth embedding
        config = SentenceTransformersConfig.create(
            model="nomic-ai/nomic-embed-text-v1.5", dimensions=768
        )
        emb_name, config = await cat3.add_embedding(con, config)
        assert emb_name == "emb4"
        assert isinstance(config, SentenceTransformersConfig)
        assert config.model == "nomic-ai/nomic-embed-text-v1.5"
        assert config.dimensions == 768

        async with con.cursor(row_factory=dict_row) as cur:
            # we should have 3 semantic catalogs
            await cur.execute("select count(*) as actual from ai.semantic_catalog")
            row = await cur.fetchone()
            assert row is not None
            actual: int = int(row["actual"])
            assert actual == 3
            # check how many embeddings each catalog has
            await cur.execute("""\
                select c.catalog_name, count(*) as num
                from ai.semantic_catalog_embedding e
                inner join ai.semantic_catalog c on (e.semantic_catalog_id = c.id)
                group by 1
            """)
            for row in await cur.fetchall():
                match row["catalog_name"]:
                    case "default" | "cat2":
                        assert row["num"] == 1
                    case "cat3":
                        assert row["num"] == 3
                    case _:
                        raise AssertionError("unexpected semantic catalog")
            # make sure the vector columns exist
            await cur.execute("""\
                select a.attnum, a.attname, format_type(a.atttypid, a.atttypmod) as type
                from pg_class k
                inner join pg_namespace n on (k.relnamespace = n.oid)
                inner join pg_attribute a on (k.oid = a.attrelid)
                where n.nspname = 'ai'
                and k.relname = 'semantic_catalog_obj_3'
                and a.attnum > 0
                and not a.attisdropped
                and format_type(a.atttypid, a.atttypmod) ~ '^vector\\([0-9]+\\)$'
                order by a.attnum
            """)
            for row in await cur.fetchall():
                match row["attnum"]:
                    case 10:
                        assert row["attname"] == "vec1"
                        assert row["type"] == "vector(768)"
                    case 12:
                        assert row["attname"] == "emb3"
                        assert row["type"] == "vector(768)"
                    case 13:
                        assert row["attname"] == "emb4"
                        assert row["type"] == "vector(768)"
                    case _:
                        raise AssertionError("unexpected vector column")

    # try to add a semantic catalog with a bad name
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        with pytest.raises(psycopg.errors.CheckViolation):
            await sc.create(con, catalog_name="MyCatalog")

    # add a semantic catalog with explicit embedding
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        config = OpenAIConfig.create(model="text-embedding-ada-002", dimensions=1536)
        cat1 = await sc.create(
            con,
            catalog_name="name_checks",
            embedding_name="vec1",
            embedding_config=config,
        )
        assert cat1.name == "name_checks"
        embs = await cat1.list_embeddings(con)
        assert len(embs) == 1
        emb_name, config = embs[0]
        assert emb_name == "vec1"
        assert isinstance(config, OpenAIConfig)

    # try to add a second embedding with a bad name
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        config = OpenAIConfig.create(model="text-embedding-ada-002", dimensions=1536)
        with pytest.raises(psycopg.errors.CheckViolation):
            await cat1.add_embedding(con, config, embedding_name="This is A bad name")

    # test dropping a semantic catalog
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        await cat1.drop(con)
        async with con.cursor(row_factory=dict_row) as cur:
            await cur.execute("select count(*) as actual from ai.semantic_catalog")
            row = await cur.fetchone()
            assert row is not None
            actual: int = int(row["actual"])
            assert actual == 3


async def test_semantic_catalog_getters(container: PostgresContainer):
    async with (
        await psycopg.AsyncConnection.connect(
            container.connection_string(database=DATABASE)
        ) as con,
        con.transaction(force_rollback=True) as _,
    ):
        cat1 = await sc.create(con, catalog_name="butch1")
        assert cat1.name == "butch1"
        cat2 = await sc.create(con, catalog_name="butch2")
        assert cat2.name == "butch2"
        cat3 = await sc.create(con, catalog_name="butch3")
        assert cat3.name == "butch3"
        actual = await sc.from_name(con, "butch2")
        assert actual.name == "butch2"
        assert actual.id == cat2.id
        actual = await sc.from_id(con, cat3.id)
        assert actual.name == "butch3"
        assert actual.id == cat3.id
        actuals = await sc.list_semantic_catalogs(con)
        assert len(actuals) >= 3
        assert "butch1" in {c.name for c in actuals}
        assert "butch2" in {c.name for c in actuals}
        assert "butch3" in {c.name for c in actuals}
