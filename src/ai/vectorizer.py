import json
import httpx


def get_vectorizer_config(plpy, config_id: int) -> dict:
    plan = plpy.prepare("""
        select
          id
        , source_schema
        , source_table
        , target_schema
        , target_table
        , target_column
        , queue_schema
        , queue_table
        , config
        from ai.vectorizer_config
        where id = $1
    """, ["int"])
    result = plan.execute([config_id], 1)
    if not result:
        plpy.error(f"vectorizer {config_id} config not found")
    config = {}
    for k, v in json.loads(result[0]["config"]).items():
        config[k] = v
    for colname in result.colnames():
        if colname == "config":
            continue
        config[colname] = result[0][colname]
    return config


def insert_vectorizer_execution(plpy, config_id: int, config: dict) -> int:
    plan = plpy.prepare("""
        insert into ai.vectorizer_execution
        ( config_id
        , config
        )
        values
        ( $1
        , $2
        )
        returning id
    """, ["int", "jsonb"])
    results = plan.execute([config_id, json.dumps(config)], 1)
    if results.nrows() != 1:
        plpy.error(f"vectorizer execution was not inserted")
    return results[0]["id"]


def execute_vectorizer(plpy, config_id: int) -> int:
    config = get_vectorizer_config(plpy, config_id)
    id = insert_vectorizer_execution(plpy, config_id, config)
    r = httpx.post("http://localhost:8000/", json={"id": id})
    if r.status_code != httpx.codes.OK:
        plpy.error(f"failed to signal vectorizer execution: {r.status_code}")
    resp = r.json()
    assert resp["id"] == id
    return id


def get_primary_key(plpy, source_table: int) -> list[dict]:
    plan = plpy.prepare("""
        select jsonb_agg(x) as pk
        from
        (
            select e.attnum, e.pknum, a.attname, y.typname, a.attnotnull
            from pg_catalog.pg_constraint k
            cross join lateral unnest(k.conkey) with ordinality e(attnum, pknum)
            inner join pg_catalog.pg_attribute a
                on (k.conrelid operator(pg_catalog.=) a.attrelid
                    and e.attnum operator(pg_catalog.=) a.attnum)
            inner join pg_catalog.pg_type y on (a.atttypid operator(pg_catalog.=) y.oid)
            where k.conrelid operator(pg_catalog.=) $1
            and k.contype operator(pg_catalog.=) 'p'
        ) x
    """, ["oid"])
    results = plan.execute([source_table])
    if not results:
        plpy.error("source table must have a primary key constraint")
    return [{k: r[k] for k in results.colnames()} for r in results]
