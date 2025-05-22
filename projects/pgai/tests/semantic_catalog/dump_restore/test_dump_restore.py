import subprocess
from pathlib import Path

import psycopg

import pgai
import pgai.semantic_catalog as sc
from pgai.semantic_catalog.vectorizer import OllamaConfig, OpenAIConfig
from tests.semantic_catalog.utils import PostgresContainer


async def setup(dump_url: str) -> None:
    pgai.install(dump_url)
    async with await psycopg.AsyncConnection.connect(dump_url) as con:
        catalog = await sc.create(con)
        assert catalog.id == 1, "catalog.id is not 1"
        assert catalog.name == "default", "catalog.name is not 'default'"
        # add a second embedding config
        await catalog.add_embedding(
            con,
            OpenAIConfig.create(
                model="text-embedding-3-small",
                dimensions=1536,
            ),
        )
        # add a third embedding config
        await catalog.add_embedding(
            con,
            OllamaConfig.create(
                model="nomic-embed-text",
                dimensions=768,
            ),
        )
        async with con.cursor() as cur:
            script = Path(__file__).parent.joinpath("vector_dump.sql").read_text()
            await cur.execute(script)  # pyright: ignore [reportArgumentType]
            await cur.execute("select count(*) from ai.semantic_catalog_obj_1")
            row = await cur.fetchone()
            assert row is not None, "no result for count of semantic_catalog_obj_1"
            assert row[0] > 0
            await cur.execute("select ai.sc_grant_admin('ada')")
            await cur.execute("select ai.sc_grant_write('default', 'vera')")
            await cur.execute("select ai.sc_grant_read('default', 'edith')")


async def test_dump_restore(container: PostgresContainer):
    container.drop_database("dump")
    container.drop_database("restore")

    container.drop_user("ada")
    container.drop_user("vera")
    container.drop_user("edith")
    container.drop_user("bot")

    container.create_database("restore")
    container.create_database("dump")

    container.create_user("ada")
    container.create_user("vera")
    container.create_user("edith")
    container.create_user("bot")

    dump_url = container.connection_string(database="dump")
    restore_url = container.connection_string(database="restore")
    await setup(dump_url)

    dump_expected = Path(__file__).parent.joinpath("dump.expected")
    dump_actual = Path(__file__).parent.joinpath("dump.actual")
    privs_expected = Path(__file__).parent.joinpath("privs.expected").read_text()

    dump_expected.unlink(missing_ok=True)
    dump_actual.unlink(missing_ok=True)

    # dump the dump db
    cp = subprocess.run(
        " ".join(
            [
                f'docker exec -w "/tmp/tests/dump_restore" {container.name}',
                'pg_dump -d "postgres://postgres@localhost:5432/dump"',
                "-F p --schema=postgres_air --schema=ai",
                "-f dump.expected",
            ]
        ),
        text=True,
        shell=True,
        capture_output=True,
    )
    assert cp.returncode == 0, f"dump of dump db failed: {cp.stderr}"

    assert dump_expected.exists(), "dump.expected does not exist"

    # get the privileges in the dump db
    cp = subprocess.run(
        " ".join(
            [
                f'docker exec -w "/tmp/tests/dump_restore" {container.name}',
                'psql -d "postgres://postgres@localhost:5432/dump"',
                "-X",
                "-P format=aligned",
                "-f privs.sql",
                "-o privs_dump.actual",
            ]
        ),
        text=True,
        shell=True,
        capture_output=True,
    )
    assert cp.returncode == 0, f"dump of dump db privs failed: {cp.stderr}"
    privs_actual = Path(__file__).parent.joinpath("privs_dump.actual").read_text()
    assert privs_actual == privs_expected

    # install pgvector in restore db
    async with (
        await psycopg.AsyncConnection.connect(restore_url) as con,
        con.cursor() as cur,
    ):
        await cur.execute("create extension vector")

    # restore to the restore db
    cp = subprocess.run(
        " ".join(
            [
                f'docker exec -w "/tmp/tests/dump_restore" {container.name}',
                'psql -d "postgres://postgres@localhost:5432/restore"',
                "-v ON_ERROR_STOP=1",
                "-f dump.expected",
            ]
        ),
        text=True,
        shell=True,
        capture_output=True,
    )
    assert cp.returncode == 0, f"restore to the restore db failed: {cp.stderr}"

    # dump the restore db
    cp = subprocess.run(
        " ".join(
            [
                f'docker exec -w "/tmp/tests/dump_restore" {container.name}',
                'pg_dump -d "postgres://postgres@localhost:5432/restore"',
                "-F p --schema=postgres_air --schema=ai",
                "-f dump.actual",
            ]
        ),
        text=True,
        shell=True,
        capture_output=True,
    )
    assert cp.returncode == 0, f"dump of the restore db failed: {cp.stderr}"

    # compare dump files of restore and dump databases
    expected = dump_expected.read_text()
    actual = dump_actual.read_text()
    assert expected == actual

    # get the privileges in the restore db
    cp = subprocess.run(
        " ".join(
            [
                f'docker exec -w "/tmp/tests/dump_restore" {container.name}',
                'psql -d "postgres://postgres@localhost:5432/restore"',
                "-X",
                "-P format=aligned",
                "-f privs.sql",
                "-o privs_restore.actual",
            ]
        ),
        text=True,
        shell=True,
        capture_output=True,
    )
    assert cp.returncode == 0, f"dump of restore db privs failed: {cp.stderr}"
    privs_actual = Path(__file__).parent.joinpath("privs_restore.actual").read_text()
    assert privs_actual == privs_expected

    # load the postgres air schema into the restored database
    # now, the oids of the postgres air objects won't match the semantic catalog
    cp = subprocess.run(
        " ".join(
            [
                f'docker exec -w "/tmp/tests/data" {container.name}',
                '/usr/bin/psql -d "postgres://postgres@localhost:5432/restore"',
                "-v ON_ERROR_STOP=1",
                "-f postgres_air.sql",
            ]
        ),
        text=True,
        shell=True,
        capture_output=True,
    )
    assert (
        cp.returncode == 0
    ), f"failed to load postgres_air into restore db: {cp.stderr}"

    async with (
        await psycopg.AsyncConnection.connect(restore_url, autocommit=True) as con,
        con.cursor() as cur,
    ):
        catalog = await sc.from_id(con, 1)

        # do we have all the object descriptions we expect?
        await cur.execute(f"""\
            select count(*)
            from ai.semantic_catalog_obj_{catalog.id}
        """)  # pyright: ignore [reportArgumentType]
        row = await cur.fetchone()
        assert row and row[0] == 16

        # fix the ids
        await catalog.fix_ids(con, con)

        # postgres_air.flight_summary should have been deleted
        await cur.execute(f"""\
            select count(*)
            from ai.semantic_catalog_obj_{catalog.id}
        """)  # pyright: ignore [reportArgumentType]
        row = await cur.fetchone()
        assert row and row[0] == 11

        # change the objtype to 'bob' across the board
        await cur.execute(f"""\
            update ai.semantic_catalog_obj_{catalog.id}
            set objtype = 'bob'
        """)  # pyright: ignore [reportArgumentType]

        # fix the names
        await catalog.fix_names(con, con)

        # objtype should have been fixed
        await cur.execute(f"""\
            select count(*)
            from ai.semantic_catalog_obj_{catalog.id}
            where objtype != 'bob'
        """)  # pyright: ignore [reportArgumentType]
        row = await cur.fetchone()
        assert row and row[0] == 11

        # swap the names of two tables
        async with con.transaction() as _:
            await cur.execute("""\
                create table postgres_air.bob();
                select ai.sc_set_table_desc
                ( 'postgres_air.bob'::regclass
                , 'this table has no columns'
                );
                alter table postgres_air.airport rename to fred;
                alter table postgres_air.bob rename to airport;
                alter table postgres_air.fred rename to bob;
            """)

        # fix the names
        await catalog.fix_names(con, con)

        # objnames should have been fixed
        await cur.execute(f"""\
            select description
            from ai.semantic_catalog_obj_{catalog.id}
            where objnames = array['postgres_air', 'airport']
        """)  # pyright: ignore [reportArgumentType]
        row = await cur.fetchone()
        assert row and row[0] == "this table has no columns"

        await cur.execute("""\
            select ai.sc_grant_read('default', 'bot');
            select ai.sc_grant_obj_read('default', 'bot');
        """)

    # get the bot's privileges to the objects
    cp = subprocess.run(
        " ".join(
            [
                f'docker exec -w "/tmp/tests/dump_restore" {container.name}',
                'psql -d "postgres://postgres@localhost:5432/restore"',
                "-X",
                "-P format=aligned",
                "-f obj_privs.sql",
                "-o obj_privs.actual",
            ]
        ),
        text=True,
        shell=True,
        capture_output=True,
    )
    assert cp.returncode == 0, f"dump of obj privs failed: {cp.stderr}"
    obj_actual = Path(__file__).parent.joinpath("obj_privs.actual").read_text()
    obj_expected = Path(__file__).parent.joinpath("obj_privs.expected").read_text()
    assert obj_actual == obj_expected
