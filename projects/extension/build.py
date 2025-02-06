#!/usr/bin/env python3
import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from collections import OrderedDict
from pathlib import Path


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

    def __contains__(self, item):
        """containment check for action"""
        return getattr(self, item.replace("-", "_"), None) is not None

    def __getitem__(self, key):
        """get the member function for an action, indexed by action name"""
        return getattr(self, key.replace("-", "_"))

    @classmethod
    def help(cls):
        """displays this message and exits"""
        message = "Available targets:"
        descriptions = OrderedDict()
        longest_key = 0

        def get_docstring_parts(docstring: str | None):
            if not docstring:
                return "", ""

            lines = docstring.splitlines()
            title = lines[0].strip() if lines else ""
            description = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

            return title, description

        for key in cls.__dict__.keys():
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
    def build_install(version: str | None = None) -> None:
        """runs build followed by install

        takes an optional argument, 'all' which installs all versions and their dependencies"""
        Actions.build()
        Actions.install(version)

    @staticmethod
    def install(version: str | None = None) -> None:
        """install the pgai extension

        takes an optional argument 'all' which installs all versions and their dependencies"""
        all = version is not None and version.strip() == "all"
        error_if_pre_release()
        if all:
            Actions.install_prior_py()
        Actions.install_py()
        Actions.install_sql(version)

    @staticmethod
    def install_sql(version: str | None = None) -> None:
        """installs the sql files into the postgres installation

        takes an optional argument 'all' which installs the sql for all versions"""
        all = version is not None and version.strip() == "all"
        ext_dir = extension_install_dir()
        if not ext_dir.is_dir():
            fatal(f"extension directory does not exist: {ext_dir}")
        this_sql_file = output_sql_file()
        if not this_sql_file.is_file():
            fatal(f"required sql file is missing: {this_sql_file}")
        if not control_file().is_file():
            fatal(f"required control file is missing: {control_file()}")
        for src in sql_dir().glob("ai*.control"):
            dest = ext_dir / src.name
            shutil.copyfile(src, dest)
        if all:
            for src in sql_dir().glob("ai--*.sql"):
                dest = ext_dir / src.name
                shutil.copyfile(src, dest)
        else:
            # only install sql files for this version
            for src in sql_dir().glob(f"ai*--{this_version()}.sql"):
                dest = ext_dir / src.name
                shutil.copyfile(src, dest)

    @staticmethod
    def install_prior_py() -> None:
        """installs the extension's python package for prior versions"""
        for version in prior_versions():
            if os.sep in version:
                fatal(f"'{os.sep}' in version {version}. this is not supported")
            version_target_dir = python_install_dir().joinpath(version)
            if version_target_dir.exists():
                continue
            tmp_dir = Path(tempfile.gettempdir()).joinpath("pgai", version)
            tmp_dir.mkdir(parents=True, exist_ok=True)
            branch = git_tag(version)
            subprocess.run(
                f"git clone https://github.com/timescale/pgai.git --branch {branch} {tmp_dir}",
                shell=True,
                check=True,
                env=os.environ,
            )
            tmp_src_dir = tmp_dir.joinpath("projects", "extension").resolve()
            bin = "pip3" if shutil.which("uv") is None else "uv pip"
            cmd = f'{bin} install -v --compile --target "{version_target_dir}" "{tmp_src_dir}"'
            subprocess.run(
                cmd,
                check=True,
                shell=True,
                env=os.environ,
                cwd=str(tmp_src_dir),
            )
            shutil.rmtree(tmp_dir)

    @staticmethod
    def install_py() -> None:
        """installs the extension's python package"""
        build_init_py()
        python_install_dir().mkdir(exist_ok=True)
        version = this_version()
        version_target_dir = python_install_dir().joinpath(version)
        if version_target_dir.exists():
            # if it already exists, assume the dependencies have already been installed
            # and just install *our* code. this is for development workflow speed
            d = version_target_dir.joinpath("ai")  # delete module if exists
            if d.exists():
                shutil.rmtree(d)
            for d in version_target_dir.glob(
                "pgai-*.dist-info"
            ):  # delete package info if exists
                shutil.rmtree(d)
            bin = "pip3" if shutil.which("uv") is None else "uv pip"
            cmd = f'{bin} install -v --no-deps --compile --target "{version_target_dir}" "{ext_dir()}"'
            subprocess.run(
                cmd,
                check=True,
                shell=True,
                env=os.environ,
                cwd=str(ext_dir()),
            )
        else:
            version_target_dir.mkdir(exist_ok=True)
            bin = "pip3" if shutil.which("uv") is None else "uv pip"
            cmd = f'{bin} install -v --compile --target "{version_target_dir}" "{ext_dir()}"'
            subprocess.run(
                cmd,
                check=True,
                shell=True,
                env=os.environ,
                cwd=str(ext_dir()),
            )

    @staticmethod
    def uninstall() -> None:
        """uninstalls the project"""
        Actions.uninstall_sql()
        Actions.uninstall_py()

    @staticmethod
    def uninstall_sql() -> None:
        """removes the sql extension from the postgres installation"""
        ext_dir = extension_install_dir()
        if not ext_dir.exists():
            return
        for f in ext_dir.glob("ai*.control"):
            f.unlink()
        for f in ext_dir.glob("ai--*.sql"):
            f.unlink()

    @staticmethod
    def uninstall_py() -> None:
        """removes the extension's python package from the system"""
        shutil.rmtree(python_install_dir(), ignore_errors=True)

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
    def build() -> None:
        """alias for build-sql"""
        Actions.build_sql()

    @staticmethod
    def build_sql() -> None:
        """constructs the sql files for the extension"""
        check_versions()
        check_incremental_sql_files(incremental_sql_files())
        check_idempotent_sql_files(idempotent_sql_files())
        build_control_file()
        hr = "".rjust(80, "-")  # "horizontal rule"
        osf = output_sql_file()
        osf.unlink(missing_ok=True)
        with osf.open("w") as wf:
            wf.write(f"{hr}\n-- ai {this_version()}\n\n")
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
        for prior_version in prior_versions():
            if prior_version in deprecated_versions():
                # we don't allow upgrades from these versions. they are deprecated
                continue
            if is_prerelease(prior_version):
                # we don't allow upgrades from prerelease versions
                continue
            dest = sql_dir().joinpath(f"ai--{prior_version}--{this_version()}.sql")
            dest.unlink(missing_ok=True)
            shutil.copyfile(osf, dest)

    @staticmethod
    def clean() -> None:
        """removes python build artifacts from the src dir"""
        Actions.clean_sql()
        Actions.clean_py()

    @staticmethod
    def clean_sql() -> None:
        """removes sql file artifacts from the sql dir"""
        for f in sql_dir().glob(f"ai--*.*.*--{this_version()}.sql"):
            f.unlink(missing_ok=True)
        output_sql_file().unlink(missing_ok=True)

    @staticmethod
    def clean_py() -> None:
        """removes python build artifacts from the extension src dir"""
        d = ext_dir().joinpath("build")
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
        d = ext_dir().joinpath("pgai.egg-info")
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)

    @staticmethod
    def build_release() -> None:
        """runs build-sql and updates the version in __init__.py"""
        Actions.clean_sql()
        Actions.clean_py()
        Actions.build()
        build_init_py()
        Actions.freeze()

    @staticmethod
    def test() -> None:
        """runs the tests in the docker container"""
        subprocess.run(
            "uv run pytest", shell=True, check=True, env=os.environ, cwd=tests_dir()
        )

    @staticmethod
    def test_server() -> None:
        """runs the test http server in the docker container"""
        if where_am_i() == "host":
            cmd = "docker exec -it -w /pgai/tests/vectorizer pgai-ext fastapi dev server.py"
            subprocess.run(cmd, shell=True, check=True, env=os.environ, cwd=ext_dir())
        else:
            cmd = "uv run fastapi dev server.py"
            subprocess.run(
                cmd,
                shell=True,
                check=True,
                env=os.environ,
                cwd=tests_dir().joinpath("vectorizer"),
            )

    @staticmethod
    def lint_sql() -> None:
        """runs pgspot against the `ai--<this_version>.sql` file"""
        sql = sql_dir().joinpath(f"ai--{this_version()}.sql")
        cmd = " ".join(
            [
                "pgspot --ignore-lang=plpython3u",
                '--proc-without-search-path "ai._vectorizer_job(job_id integer,config pg_catalog.jsonb)"',
                f"{sql}",
            ]
        )
        subprocess.run(cmd, shell=True, check=True, env=os.environ)

    @staticmethod
    def lint_py() -> None:
        """runs ruff linter against the python source files"""
        subprocess.run(
            f"uv run ruff check {ext_dir()}", shell=True, check=True, env=os.environ
        )

    @staticmethod
    def lint() -> None:
        """runs both sql and python linters"""
        Actions.lint_py()
        Actions.lint_sql()

    @staticmethod
    def format_py() -> None:
        """runs ruff to check formatting of the python source files"""
        subprocess.run(
            f"uv run ruff format --diff {ext_dir()}",
            shell=True,
            check=True,
            env=os.environ,
        )

    @staticmethod
    def reformat_py() -> None:
        """runs ruff to update the formatting of the python source files"""
        subprocess.run(
            f"ruff format {ext_dir()}", shell=True, check=True, env=os.environ
        )

    @staticmethod
    def check_requirements() -> None:
        """verifies that requirements-lock.txt is up to date with pyproject.toml"""
        if shutil.which("uv") is None:
            fatal("uv not found")

        # Create a temporary file to store current requirements
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt") as tmp_file:
            # Generate current requirements
            subprocess.run(
                f"uv export --quiet --format requirements-txt -o {tmp_file.name}",
                shell=True,
                check=True,
                env=os.environ,
                text=True,
            )

            # Read both files
            lock_file = ext_dir() / "requirements-lock.txt"
            if not lock_file.exists():
                fatal(
                    "requirements-lock.txt does not exist. Run 'uv export --format requirements-txt -o requirements-lock.txt' to create it."
                )

            from difflib import unified_diff

            with open(lock_file) as f1, open(tmp_file.name) as f2:
                # Skip the first 3 lines when reading both files since the contain a line with the file name
                # which will always be different
                lock_contents = f1.readlines()[3:]
                current_contents = f2.readlines()[3:]

                diff = list(unified_diff(lock_contents, current_contents))
                if diff:
                    fatal(
                        "requirements-lock.txt is out of sync with uv.lock.\n"
                        "Run 'uv export --format requirements-txt -o requirements-lock.txt' to update it.\n"
                        + "".join(diff)
                    )

    @staticmethod
    def docker_build() -> None:
        """builds the dev docker image"""
        subprocess.run(
            f"""docker build --build-arg PG_MAJOR={pg_major()} -t pgai-ext .""",
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
                "docker run -d --name pgai-ext --hostname pgai-ext -e POSTGRES_HOST_AUTH_METHOD=trust",
                networking,
                f"--mount type=bind,src={ext_dir()},dst=/pgai",
                "--mount type=volume,dst=/pgai/.venv",
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
                "pgai-ext",
                "-c shared_preload_libraries='timescaledb, pgextwlist'",
                "-c extwlist.extensions='ai,vector'",
            ]
        )
        subprocess.run(cmd, shell=True, check=True, env=os.environ, text=True)

    @staticmethod
    def docker_start() -> None:
        """starts the container"""
        subprocess.run(
            """docker start pgai-ext""",
            shell=True,
            check=True,
            env=os.environ,
            text=True,
        )

    @staticmethod
    def docker_stop() -> None:
        """stops the container"""
        subprocess.run(
            """docker stop pgai-ext""",
            shell=True,
            check=True,
            env=os.environ,
            text=True,
        )

    @staticmethod
    def docker_rm() -> None:
        """deletes the dev container"""
        subprocess.run(
            """docker rm --force --volumes pgai-ext""",
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
        cmd = "docker exec pgai-ext make build-install"
        subprocess.run(cmd, shell=True, check=True, env=os.environ, cwd=ext_dir())
        cmd = 'docker exec -u postgres pgai-ext psql -c "create extension ai cascade"'
        subprocess.run(cmd, shell=True, check=True, env=os.environ, cwd=ext_dir())
        cmd = "docker exec -it -d -w /pgai/tests pgai-ext fastapi dev server.py"
        subprocess.run(cmd, shell=True, check=True, env=os.environ, cwd=ext_dir())


def versions() -> list[str]:
    # ADD NEW VERSIONS TO THE FRONT OF THIS LIST! STAY SORTED PLEASE
    return [
        "0.8.1-dev",
        "0.8.0",  # released
        "0.7.0",  # released
        "0.6.0",  # released
        "0.5.0",  # released
        "0.4.1",  # released
        "0.4.0",  # released
    ]


def this_version() -> str:
    return versions()[0]


def prior_versions() -> list[str]:
    return versions()[1:] if len(versions()) > 1 else []


def deprecated_versions() -> set[str]:
    return set()


def fatal(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(1)


def check_versions():
    # double-hyphens will cause issues. disallow
    pattern = r"\d+\.\d+\.\d+(-[a-z0-9.]+)?"
    for version in versions():
        if re.fullmatch(pattern, version) is None:
            fatal(f"version {version} does not match the pattern {pattern}")


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


def pg_major() -> str | None:
    return os.getenv("PG_MAJOR")


def ext_dir() -> Path:
    return Path(__file__).resolve().parent


def sql_dir() -> Path:
    return ext_dir() / "sql"


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
    return int(match.group(1))


def check_sql_file_order(path: Path, prev: int) -> int:
    kind = path.parent.name
    this = sql_file_number(path)
    # ensuring file number correlation
    if this < 900 and this != prev + 1:
        fatal(f"{kind} sql files must be strictly ordered. this: {this} prev: {prev}")
    # avoiding file number duplication
    if this >= 900 and this == prev:  # allow gaps in pre-production scripts
        fatal(
            f"{kind} sql files must not have duplicate numbers. this: {this} prev: {prev}"
        )
    ff = parse_feature_flag(path)
    # feature flagged files should be between 900 and 999
    if this < 900 and ff:
        fatal(
            f"{kind} sql files under 900 must be NOT gated by a feature flag: {path.name}"
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
        prev = check_sql_file_order(path, prev)
        if path.name in frozen:
            if hash_file(path) != frozen[path.name]:
                fatal(
                    f"changing frozen incremental sql file {path.name} is not allowed"
                )


def output_sql_file() -> Path:
    return sql_dir() / f"ai--{this_version()}.sql"


def control_file() -> Path:
    return sql_dir() / "ai.control"


def build_control_file() -> None:
    content = control_file().read_text()
    lines = []
    for line in content.splitlines(keepends=True):
        if line.startswith("default_version"):
            lines.append(f"default_version='{this_version()}'\n")
        else:
            lines.append(line)
    control_file().write_text("".join(lines))


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
    version = this_version()
    migration_body = migration_body.replace("@extversion@", version)
    code = template.format(
        migration_name=migration_name,
        migration_body=migration_body,
        version=version,
    )
    feature_flag = parse_feature_flag(input_file)
    if feature_flag:
        code = gate_sql(code, feature_flag)
    return code


def build_idempotent_sql_file(input_file: Path) -> str:
    inject = f"""
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '{python_install_dir()}') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("{this_version()}")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("{this_version()}" == ai_version)
        GD["ai.version"] = "{this_version()}"
    else:
        if GD["ai.version"] != "{this_version()}":
            plpy.fatal("the pgai extension version has changed. start a new session")
    """
    # keep leading indentation
    # remove first and last (blank) lines
    inject = "".join(inject.splitlines(keepends=True)[1:-1])
    code = input_file.read_text()
    code = code.replace("@extversion@", this_version())
    code = code.replace(
        """    #ADD-PYTHON-LIB-DIR\n""", inject
    )  # leading 4 spaces is intentional
    feature_flag = parse_feature_flag(input_file)
    if feature_flag:
        code = gate_sql(code, feature_flag)
    return code


def build_feature_flags() -> str:
    feature_flags = set()
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
        output += template.format(
            feature_flag=feature_flag, guc=guc, version=this_version()
        )
    return output


def postgres_bin_dir() -> Path:
    bin_dir = os.getenv("PG_BIN")
    if bin_dir is not None and Path(bin_dir).is_dir():
        return Path(bin_dir).resolve()
    else:
        bin_dir = Path(f"/usr/lib/postgresql/{pg_major()}/bin")
        if bin_dir.is_dir():
            return bin_dir.resolve()
        else:
            p = shutil.which("pg_config")
            if not p:
                fatal("pg_config not found")
            return Path(p).parent.resolve()


def pg_config() -> Path:
    return postgres_bin_dir() / "pg_config"


def extension_install_dir() -> Path:
    proc = subprocess.run(
        f"{pg_config()} --sharedir",
        check=True,
        shell=True,
        env=os.environ,
        text=True,
        capture_output=True,
    )
    return Path(str(proc.stdout).strip()).resolve() / "extension"


def python_install_dir() -> Path:
    # think long and hard before you change this path
    # don't do it. i'm warning you
    # seriously.
    # you'll wreck old versions. look at build_idempotent_sql_file()
    return Path(
        "/usr/local/lib/pgai"
    ).resolve()  # CONTROLS WHERE THE PYTHON LIB AND DEPS ARE INSTALLED


def build_init_py() -> None:
    # ai/__init__.py is checked in to version control. So, all the previous
    # versions will have the file with the correct version already in it. This
    # function just ensures that you can't screw up the current version. The
    # only place you have to update the version when starting a new release is
    # in the versions() function.
    init_py = ext_dir().joinpath("ai", "__init__.py").resolve()
    content = init_py.read_text()
    lines = []
    for line in content.splitlines(keepends=True):
        if line.startswith("__version__"):
            lines.append(f'__version__ = "{this_version()}"\n')
        else:
            lines.append(line)
    init_py.write_text("".join(lines))


def error_if_pre_release() -> None:
    # Note: released versions always have the output sql file commited into the repository.
    output_file = output_sql_file()
    command = (
        "just ext build-install"
        if "ROOT_JUSTFILE" in os.environ
        else "just build-install"
        if "PROJECT_JUSTFILE" in os.environ
        else "python3 build.py build-install"
    )
    if not Path(output_file).exists():
        print(
            textwrap.dedent(f"""
                WARNING: You're trying to install a pre-release version of pgai.
                This is not supported, and there is no upgrade path.

                Instead, install an official release from https://github.com/timescale/pgai/releases.

                If you are certain that you want to install a pre-release version, run:
                    `{command}`
            """)
        )
        exit(1)


def tests_dir() -> Path:
    return ext_dir().joinpath("tests").absolute()


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
    functions = []
    while i < len(sys.argv):
        action = sys.argv[i]
        if action in actions:
            # check if next item in argv is potentially an arg to the current action
            arg = None
            if len(sys.argv) > i + 1 and sys.argv[i + 1] not in actions:
                arg = sys.argv[i + 1]
                i += 1
            fn = actions[action]
            functions.append((fn, arg))
            i += 1
        else:
            print(f"{action} is not a valid action", file=sys.stderr)
            sys.exit(1)
    for fn, arg in functions:
        if arg is not None:
            fn(arg)
        else:
            fn()
