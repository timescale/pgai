import time


def get_guc_value(plpy, setting: str, default: str) -> str:
    plan = plpy.prepare("select pg_catalog.current_setting($1, true) as val", ["text"])
    result = plan.execute([setting], 1)
    val: str | None = None
    if len(result) != 0:
        val = result[0]["val"]
    if val is None:
        val = default
    return val


class VerboseRequestTrace:
    def __init__(self, plpy, name: str, verbose: bool):
        self.plpy = plpy
        self.name = name
        self.verbose = verbose

    def __enter__(self):
        if self.verbose:
            self.start_time = time.time()
            self.plpy.info(f"sending a request for {self.name}...")

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        if self.verbose:
            self.plpy.info(
                f"{self.name} returned in {time.time() - self.start_time:.3f} seconds"
            )
