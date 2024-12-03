def get_guc_value(plpy, setting: str, default: str) -> str:
    plan = plpy.prepare("select pg_catalog.current_setting($1, true) as val", ["text"])
    result = plan.execute([setting], 1)
    val: str | None = None
    if len(result) != 0:
        val = result[0]["val"]
    if val is None:
        val = default
    return val
