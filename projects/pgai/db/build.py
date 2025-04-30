#!/usr/bin/env python3
import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path
from typing import cast


class Actions:
    """Collects all actions which the build.py script supports

    Actions are derived from public member functions of this class.
    Action names are kebab-case, by doing a `.replace("_", "-")` on the method.
    e.g. `def build_install` becomes the action `build-install`.

    The help text is auto-generated from the member function name and docblock.

    The containment check is aware of this difference, so the following works:
    ```
        actions = Actions()
        if "build-install" in actions:
            print "true"
    ```

    To get the action function for an action name, use indexed access:

    ```
        actions = BuildPuActions()
        action_name = "build-install"
        action_function = actions[action_name]
        action_function()
    ```
    """

    def __contains__(self, item: str) -> bool:
        """containment check for action"""
        return getattr(self, item.replace("-", "_"), None) is not None

    def __getitem__(self, key: str) -> Callable[[], None] | Callable[[str], None]:
        """get the member function for an action, indexed by action name"""
        return getattr(self, key.replace("-", "_"))

    @classmethod
    def help(cls):
        """displays this message and exits"""
        message = "Available targets:"
        descriptions: OrderedDict[str, tuple[str, str]] = OrderedDict()
        longest_key = 0

        def get_docstring_parts(docstring: str | None):
            if not docstring:
                return "", ""

            lines = docstring.splitlines()
            title = lines[0].strip() if lines else ""
            description = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

            return title, description

        for key in cls.__dict__:
            if key.startswith("_"):
                # ignore private methods
                continue
            title, description = get_docstring_parts(getattr(cls, key).__doc__)
            key = key.replace("_", "-")
            longest_key = len(key) if len(key) > longest_key else longest_key
            descriptions[key] = (title, description)
        for key, (title, description) in descriptions.items():
            message += f"\n- {key: <{longest_key + 2}}{title}"
            if description != "":
                message += f"\n{'':{longest_key + 4}}{description}"
        print(message)

    @staticmethod
    def freeze() -> None:
        """updates frozen.txt with hashes of incremental sql files"""
        lines: list[str] = []
        for file in incremental_sql_files():
            if sql_file_number(file) >= 900:
                break
            lines.append(f"{hash_file(file)} {file.name}")
        frozen_file().write_text("\n".join(lines))

    @staticmethod
    def build(check: str | None = None) -> None:
        """constructs the sql files for the extension"""
        check_incremental_sql_files(incremental_sql_files())
        check_idempotent_sql_files(idempotent_sql_files())
        hr = "".rjust(80, "-")  # "horizontal rule"
        osf = output_sql_file()
        osf.unlink(missing_ok=True)
        with osf.open("w") as wf:
            wf.write(f"{hr}\n-- ai {this_version()} (x-release-please-version)\n\n")
            wf.write(sql_dir().joinpath("head.sql").read_text())
            if is_prerelease(this_version()):
                wf.write("\n\n")
                wf.write(build_feature_flags())
            wf.write("\n\n")
            for inc_file in incremental_sql_files():
                if sql_file_number(inc_file) >= 900 and not is_prerelease(
                    this_version()
                ):
                    # don't include pre-release code in non-prerelease versions
                    continue
                code = build_incremental_sql_file(inc_file)
                wf.write(code)
                wf.write("\n\n")
            for idm_file in idempotent_sql_files():
                nbr = sql_file_number(idm_file)
                if nbr != 999 and nbr >= 900 and not is_prerelease(this_version()):
                    # don't include pre-release code in non-prerelease versions
                    continue
                wf.write(f"{hr}\n-- {idm_file.name}\n")
                wf.write(build_idempotent_sql_file(idm_file))
                wf.write("\n\n")
            wf.flush()
            wf.close()
        if check:
            expected = output_sql_file().read_text()
            actual = lib_sql_file().read_text()
            if expected != actual:
                fatal("built sql file does not match sql file in library")
        else:
            shutil.copyfile(osf, lib_sql_file())

    @staticmethod
    def clean() -> None:
        """removes sql file artifacts from the sql dir"""
        for f in output_sql_dir().glob(f"ai--*.*.*--{this_version()}.sql"):
            f.unlink(missing_ok=True)
        output_sql_file().unlink(missing_ok=True)

    @staticmethod
    def test() -> None:
        """runs the tests in the docker container"""
        subprocess.run(
            "uv run --no-project pytest",
            shell=True,
            check=True,
            env=os.environ,
            cwd=tests_dir(),
        )

    @staticmethod
    def test_server() -> None:
        """runs the test http server in the docker container"""
        if where_am_i() == "host":
            cmd = "docker exec -it -w /pgai/projects/extension/tests/vectorizer pgai-db fastapi dev server.py"  # noqa: E501
            subprocess.run(cmd, shell=True, check=True, env=os.environ, cwd=db_dir())
        else:
            cmd = "uv run --no-project fastapi dev server.py"
            subprocess.run(
                cmd,
                shell=True,
                check=True,
                env=os.environ,
                cwd=tests_dir().joinpath("vectorizer"),
            )

    @staticmethod
    def lint() -> None:
        """runs pgspot against the `ai--<this_version>.sql` file"""
        cmd = " ".join(
            [
                "uv run --no-project pgspot --ignore-lang=plpython3u",
                '--proc-without-search-path "ai._vectorizer_job(job_id integer,config pg_catalog.jsonb)"',  # noqa: E501
                "--ignore PS010",  # allow creating the ai schema TODO: check if this is safe # noqa: E501
                f"{lib_sql_file()}",
            ]
        )
        subprocess.run(cmd, shell=True, check=True, env=os.environ)

    @staticmethod
    def docker_build() -> None:
        """builds the dev docker image"""
        subprocess.run(
            " ".join(
                [
                    "docker build",
                    f"--build-arg PG_MAJOR={pg_major()}",
                    "--target pgai-lib-db-dev",
                    "-t pgai-db",
                    f"--file {ext_dir()}/Dockerfile",
                    f"{ext_dir()}",
                ]
            ),
            shell=True,
            check=True,
            env=os.environ,
            text=True,
            cwd=ext_dir(),
        )

    @staticmethod
    def docker_run() -> None:
        """launches a container in docker using the docker image"""
        networking = (
            "--network host"
            if platform.system() == "Linux"
            else "-p 127.0.0.1:5432:5432"
        )
        cmd = " ".join(
            [
                "docker run -d --name pgai-db --hostname pgai-db",
                "-e POSTGRES_HOST_AUTH_METHOD=trust",
                networking,
                f"--mount type=bind,src={db_dir().parent.parent.parent},dst=/pgai",
                "-w /pgai/projects/pgai/db",
                "-e OPENAI_API_KEY",
                "-e COHERE_API_KEY",
                "-e MISTRAL_API_KEY",
                "-e VOYAGE_API_KEY",
                "-e HUGGINGFACE_API_KEY",
                "-e AZURE_API_KEY",
                "-e AZURE_API_BASE",
                "-e AZURE_API_VERSION",
                "-e AWS_ACCESS_KEY_ID",
                "-e AWS_REGION_NAME",
                "-e AWS_SECRET_ACCESS_KEY",
                "-e VERTEX_CREDENTIALS",
                "-e TEST_ENV_SECRET=super_secret",
                "pgai-db",
                "-c shared_preload_libraries='timescaledb, pgextwlist'",
                "-c extwlist.extensions='ai,vector'",
            ]
        )
        subprocess.run(cmd, shell=True, check=True, env=os.environ, text=True)

    @staticmethod
    def docker_sync() -> None:
        # install the pgai library in the container
        subprocess.run(
            " ".join(
                [
                    "docker exec pgai-db",
                    "uv sync",
                    "--directory /pgai/projects/pgai",
                    "--all-extras",
                    "--active",
                ]
            ),
            shell=True,
            check=True,
            env=os.environ,
            text=True,
        )

    @staticmethod
    def docker_start() -> None:
        """starts the container"""
        subprocess.run(
            """docker start pgai-db""",
            shell=True,
            check=True,
            env=os.environ,
            text=True,
        )

    @staticmethod
    def docker_stop() -> None:
        """stops the container"""
        subprocess.run(
            """docker stop pgai-db""",
            shell=True,
            check=True,
            env=os.environ,
            text=True,
        )

    @staticmethod
    def docker_shell() -> None:
        """launches a bash shell in the container"""
        subprocess.run(
            """docker exec -it -u root pgai-db /bin/bash""",
            shell=True,
            check=True,
            env=os.environ,
            text=True,
        )

    @staticmethod
    def docker_rm() -> None:
        """deletes the dev container"""
        subprocess.run(
            """docker rm --force --volumes pgai-db""",
            shell=True,
            check=True,
            env=os.environ,
            text=True,
        )

    @staticmethod
    def run() -> None:
        """builds+runs the dev container and installs the extension"""
        Actions.docker_build()
        Actions.docker_run()
        cmd = "docker exec pgai-db make build-install"
        subprocess.run(cmd, shell=True, check=True, env=os.environ, cwd=db_dir())
        cmd = 'docker exec -u postgres pgai-db psql -c "create extension ai cascade"'
        subprocess.run(cmd, shell=True, check=True, env=os.environ, cwd=db_dir())
        cmd = "docker exec -it -d -w /pgai/tests pgai-db fastapi dev server.py"
        subprocess.run(cmd, shell=True, check=True, env=os.environ, cwd=db_dir())


def this_version() -> str:
    init_path = os.path.join(os.path.dirname(__file__), "..", "pgai", "__init__.py")
    with open(init_path) as f:
        content = f.read()
        version_match = re.search(r'^__version__ = ["\']([^"\']*)["\']', content, re.M)
        if version_match:
            return version_match.group(1)
    raise RuntimeError("Cannot find version string")


def fatal(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(1)


def parse_version(version: str) -> tuple[int, int, int, str | None]:
    parts = re.split(r"[.-]", version, maxsplit=4)
    return (
        int(parts[0]),
        int(parts[1]),
        int(parts[2]),
        parts[3] if len(parts) > 3 else None,
    )


def is_prerelease(version: str) -> bool:
    parts = parse_version(version)
    return parts[3] is not None


def git_tag(version: str) -> str:
    return f"extension-{version}"


def pg_major() -> str:
    return os.getenv("PG_MAJOR", "17")


def db_dir() -> Path:
    return Path(__file__).resolve().parent


def lib_dir() -> Path:
    return db_dir().parent


def ext_dir() -> Path:
    return lib_dir().parent / "extension"


def lib_data_dir() -> Path:
    return lib_dir() / "pgai" / "data"


def lib_sql_file() -> Path:
    return lib_data_dir() / "ai.sql"


def sql_dir() -> Path:
    return db_dir() / "sql"


def output_sql_dir() -> Path:
    return sql_dir() / "output"


def idempotent_sql_dir() -> Path:
    return sql_dir() / "idempotent"


def idempotent_sql_files() -> list[Path]:
    paths = [
        x for x in idempotent_sql_dir().glob("*.sql") if not x.name.startswith("x")
    ]
    paths.sort()
    return paths


def incremental_sql_dir() -> Path:
    return sql_dir() / "incremental"


def incremental_sql_files() -> list[Path]:
    paths = [
        x for x in incremental_sql_dir().glob("*.sql") if not x.name.startswith("x")
    ]
    paths.sort()
    return paths


def hash_file(path: Path) -> str:
    sha256 = hashlib.sha256()
    sha256.update(path.read_bytes())
    return sha256.hexdigest()


def frozen_file() -> Path:
    return incremental_sql_dir() / "frozen.txt"


def read_frozen_file() -> dict[str, str]:
    frozen: dict[str, str] = dict()
    with frozen_file().open(mode="rt", encoding="utf-8") as r:
        for line in r.readlines():
            if line.strip() == "":
                continue
            parts = line.split(" ")
            # map file name to hash
            frozen[parts[1]] = parts[0]
    return frozen


def parse_feature_flag(path: Path) -> str | None:
    with path.open(mode="rt", encoding="utf-8") as f:
        line = f.readline()
        if not line.startswith("--FEATURE-FLAG: "):
            return None
        ff = line.removeprefix("--FEATURE-FLAG: ").strip()
        pattern = r"^[a-z_]+$"
        if re.fullmatch(pattern, ff) is None:
            fatal(
                f"feature flag {ff} in {path.name} does not match the pattern {pattern}"
            )
        return ff


def sql_file_number(path: Path) -> int:
    pattern = r"^(\d{3})-[a-z][a-z_-]*\.sql$"
    match = re.match(pattern, path.name)
    if not match:
        fatal(f"{path} file name does not match the pattern {pattern}")
    assert match is not None  # help pyright understand match cannot be None here
    return int(match.group(1))


def check_sql_file_order(path: Path, prev: int, min_strict_number: int = 0) -> int:
    kind = path.parent.name
    this = sql_file_number(path)
    # ensuring file number correlation
    if this < 900 and this >= min_strict_number and this != prev + 1:
        fatal(f"{kind} sql files must be strictly ordered. this: {this} prev: {prev}")
    # avoiding file number duplication
    if this >= 900 and this == prev:  # allow gaps in pre-production scripts
        fatal(
            f"{kind} sql files must not have duplicate numbers. this: {this} prev: {prev}"  # noqa: E501
        )
    ff = parse_feature_flag(path)
    # feature flagged files should be between 900 and 999
    if this < 900 and ff:
        fatal(
            f"{kind} sql files under 900 must be NOT gated by a feature flag: {path.name}"  # noqa: E501
        )
    # only feature flagged files go over 899
    if this >= 900 and not ff:
        fatal(f"{kind} sql files over 899 must be gated by a feature flag: {path.name}")
    return this


def check_idempotent_sql_files(paths: list[Path]) -> None:
    # paths are sorted
    prev = 0
    for path in paths:
        if path.name == "999-privileges.sql":
            break
        prev = check_sql_file_order(path, prev)


def check_incremental_sql_files(paths: list[Path]) -> None:
    # paths are sorted
    frozen = read_frozen_file()
    prev = 0
    for path in paths:
        prev = check_sql_file_order(path, prev, min_strict_number=20)
        if path.name in frozen and hash_file(path) != frozen[path.name]:
            fatal(f"changing frozen incremental sql file {path.name} is not allowed")


def output_sql_file() -> Path:
    return output_sql_dir() / f"ai--{this_version()}.sql"


def feature_flag_to_guc(feature_flag: str) -> str:
    return f"ai.enable_feature_flag_{feature_flag}"


def gate_sql(code: str, feature_flag: str) -> str:
    template = sql_dir().joinpath("gated.sql").read_text()
    guc = feature_flag_to_guc(feature_flag)
    return template.format(code=code, guc=guc, feature_flag=feature_flag)


def build_incremental_sql_file(input_file: Path) -> str:
    template = sql_dir().joinpath("migration.sql").read_text()
    migration_name = input_file.name
    migration_body = input_file.read_text()
    code = template.format(
        migration_name=migration_name,
        migration_body=migration_body,
    )
    feature_flag = parse_feature_flag(input_file)
    if feature_flag:
        code = gate_sql(code, feature_flag)
    return code


def build_idempotent_sql_file(input_file: Path) -> str:
    # keep leading indentation
    # remove first and last (blank) lines
    code = input_file.read_text()
    feature_flag = parse_feature_flag(input_file)
    if feature_flag:
        code = gate_sql(code, feature_flag)
    return code


def build_feature_flags() -> str:
    feature_flags: set[str] = set()
    for path in incremental_sql_files():
        ff = parse_feature_flag(path)
        if ff:
            feature_flags.add(ff)
    for path in idempotent_sql_files():
        ff = parse_feature_flag(path)
        if ff:
            feature_flags.add(ff)
    template = sql_dir().joinpath("flag.sql").read_text()
    output = ""
    for feature_flag in feature_flags:
        guc = feature_flag_to_guc(feature_flag)
        output += template.format(feature_flag=feature_flag, guc=guc)
    return output


def tests_dir() -> Path:
    return db_dir().joinpath("tests").absolute()


def where_am_i() -> str:
    if "WHERE_AM_I" in os.environ and os.environ["WHERE_AM_I"] == "docker":
        return "docker"
    return "host"


if __name__ == "__main__":
    actions = Actions()
    if len(sys.argv) <= 1 or "help" in sys.argv[1:]:
        actions.help()
        sys.exit(0)
    i = 1
    functions: list[
        tuple[Callable[[], None], None] | tuple[Callable[[str], None], str]
    ] = []
    while i < len(sys.argv):
        action = sys.argv[i]
        if action in actions:
            # check if next item in argv is potentially an arg to the current action
            arg = None
            if len(sys.argv) > i + 1 and sys.argv[i + 1] not in actions:
                arg = sys.argv[i + 1]
                i += 1
            fn = actions[action]
            if arg is not None:
                functions.append((cast(Callable[[str], None], fn), arg))
            else:
                functions.append((cast(Callable[[], None], fn), None))
            i += 1
        else:
            print(f"{action} is not a valid action", file=sys.stderr)
            sys.exit(1)
    for fn, arg in functions:
        if arg is not None:
            fn(arg)  # type: ignore
        else:
            fn()  # type: ignore
