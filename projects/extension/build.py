#!/usr/bin/env python3
import hashlib
import platform
import re
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


HELP = """Available targets:
- help             displays this message and exits
- build-install    runs build followed by install
- install          installs the project
- install-sql      installs the sql files into the postgres installation
- install-prior-py installs the extension's python package for prior versions
- install-py       installs the extension's python package
- uninstall        uninstalls the project
- uninstall-sql    removes the sql extension from the postgres installation
- uninstall-py     removes the extension's python package from the system
- freeze           updates frozen.txt with hashes of incremental sql files
- build            alias for build-sql
- build-sql        constructs the sql files for the extension
- clean            removes python build artifacts from the src dir
- clean-sql        removes sql file artifacts from the sql dir
- clean-py         removes python build artifacts from the extension src dir
- test             runs the tests in the docker container
- test-server      runs the test http server in the docker container
- lint-sql         runs pgspot against the `ai--<this_version>.sql` file
- lint-py          runs ruff linter against the python source files
- lint             runs both sql and python linters
- format-py        runs ruff to check formatting of the python source files
- docker-build     builds the dev docker image
- docker-run       launches a container in docker using the docker image
- docker-stop      stops the container
- docker-rm        deletes the dev container
- run              builds+runs the dev container and installs the extension"""


def versions() -> list[str]:
    # ADD NEW VERSIONS TO THE FRONT OF THIS LIST! STAY SORTED PLEASE
    return [
        "0.6.1-dev",
        "0.6.0",  # released
        "0.5.0",  # released
        "0.4.1",  # released
        "0.4.0",  # released
        "0.3.0",  # deprecated
        "0.2.0",  # deprecated
        "0.1.0",  # deprecated
    ]


def this_version() -> str:
    return versions()[0]


def prior_versions() -> list[str]:
    return versions()[1:] if len(versions()) > 1 else []


def deprecated_versions() -> set[str]:
    return {
        "0.3.0",  # deprecated
        "0.2.0",  # deprecated
        "0.1.0",  # deprecated
    }


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
    paths = [x for x in idempotent_sql_dir().glob("*.sql")]
    paths.sort()
    return paths


def incremental_sql_dir() -> Path:
    return sql_dir() / "incremental"


def incremental_sql_files() -> list[Path]:
    paths = [x for x in incremental_sql_dir().glob("*.sql")]
    paths.sort()
    return paths


def hash_file(path: Path) -> str:
    sha256 = hashlib.sha256()
    sha256.update(path.read_bytes())
    return sha256.hexdigest()


def frozen_file() -> Path:
    return incremental_sql_dir() / "frozen.txt"


def freeze() -> None:
    lines: list[str] = []
    for file in incremental_sql_files():
        if sql_file_number(file) >= 900:
            break
        lines.append(f"{hash_file(file)} {file.name}")
    frozen_file().write_text("\n".join(lines))


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
        # Note: the "old" (pre-0.4.0) packages are installed as system-level python packages
        # and take precedence over our extension-version specific packages.
        # By removing the whole thing from the path we won't run into package conflicts.
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


def build_sql() -> None:
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
            if sql_file_number(inc_file) >= 900 and not is_prerelease(this_version()):
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


def clean_sql() -> None:
    for f in sql_dir().glob(f"ai--*.*.*--{this_version()}.sql"):
        f.unlink(missing_ok=True)
    output_sql_file().unlink(missing_ok=True)


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


def install_sql() -> None:
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
    for src in sql_dir().glob("ai--*.sql"):
        dest = ext_dir / src.name
        shutil.copyfile(src, dest)


def uninstall_sql() -> None:
    ext_dir = extension_install_dir()
    if not ext_dir.exists():
        return
    for f in ext_dir.glob("ai*.control"):
        f.unlink()
    for f in ext_dir.glob("ai--*.sql"):
        f.unlink()


def python_install_dir() -> Path:
    # think long and hard before you change this path
    # don't do it. i'm warning you
    # seriously.
    # you'll wreck old versions. look at build_idempotent_sql_file()
    return Path(
        "/usr/local/lib/pgai"
    ).resolve()  # CONTROLS WHERE THE PYTHON LIB AND DEPS ARE INSTALLED


def install_old_py_deps() -> None:
    # this is necessary for versions prior to 0.4.0
    # we will deprecate these versions and then get rid of this function
    old_reqs_file = ext_dir().joinpath("old_requirements.txt").resolve()
    if old_reqs_file.is_file():
        env = {k: v for k, v in os.environ.items()}
        cmd = (
            f"pip3 install -v --compile --break-system-packages -r {old_reqs_file}"
            if shutil.which("uv") is None
            else f"uv pip install -v --compile --system --break-system-packages -r {old_reqs_file}"
        )
        subprocess.run(
            cmd,
            shell=True,
            check=True,
            env=env,
            cwd=str(ext_dir()),
        )


def install_prior_py() -> None:
    install_old_py_deps()
    for version in prior_versions():
        if version in deprecated_versions():
            # these are handled by install_old_py_deps()
            continue
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


def install_py() -> None:
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
        cmd = (
            f'{bin} install -v --compile --target "{version_target_dir}" "{ext_dir()}"'
        )
        subprocess.run(
            cmd,
            check=True,
            shell=True,
            env=os.environ,
            cwd=str(ext_dir()),
        )


def clean_py() -> None:
    d = ext_dir().joinpath("build")
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    d = ext_dir().joinpath("pgai.egg-info")
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def uninstall_py() -> None:
    shutil.rmtree(python_install_dir(), ignore_errors=True)


def uninstall() -> None:
    uninstall_sql()
    uninstall_py()


def build() -> None:
    build_sql()


def install() -> None:
    install_prior_py()
    install_py()
    install_sql()


def build_install() -> None:
    build()
    install()


def clean() -> None:
    clean_sql()
    clean_py()


def tests_dir() -> Path:
    return ext_dir().joinpath("tests").absolute()


def where_am_i() -> str:
    if "WHERE_AM_I" in os.environ and os.environ["WHERE_AM_I"] == "docker":
        return "docker"
    return "host"


def test_server() -> None:
    if where_am_i() == "host":
        cmd = """docker exec \
            -e OPENAI_API_KEY=${OPENAI_API_KEY} \
            -e ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY} \
            -e COHERE_API_KEY=${COHERE_API_KEY} \
            -e VOYAGE_API_KEY=${VOYAGE_API_KEY} \
            -it -w /pgai/tests/vectorizer pgai-ext fastapi dev server.py
            """
        subprocess.run(cmd, shell=True, check=True, env=os.environ, cwd=ext_dir())
    else:
        cmd = "fastapi dev server.py"
        subprocess.run(
            cmd,
            shell=True,
            check=True,
            env=os.environ,
            cwd=tests_dir().joinpath("vectorizer"),
        )


def test() -> None:
    subprocess.run("pytest", shell=True, check=True, env=os.environ, cwd=tests_dir())


def lint_sql() -> None:
    sql = sql_dir().joinpath(f"ai--{this_version()}.sql")
    cmd = " ".join(
        [
            "pgspot --ignore-lang=plpython3u",
            '--proc-without-search-path "ai._vectorizer_job(job_id integer,config pg_catalog.jsonb)"',
            f"{sql}",
        ]
    )
    subprocess.run(cmd, shell=True, check=True, env=os.environ)


def lint_py() -> None:
    subprocess.run(f"ruff check {ext_dir()}", shell=True, check=True, env=os.environ)


def lint() -> None:
    lint_py()
    # lint_sql()  # TODO: enable this when pgspot is fixed


def format_py() -> None:
    subprocess.run(
        f"ruff format --diff {ext_dir()}", shell=True, check=True, env=os.environ
    )


def docker_build() -> None:
    subprocess.run(
        f"""docker build --build-arg PG_MAJOR={pg_major()} -t pgai-ext .""",
        shell=True,
        check=True,
        env=os.environ,
        text=True,
        cwd=ext_dir(),
    )


def docker_run() -> None:
    networking = (
        "--network host" if platform.system() == "Linux" else "-p 127.0.0.1:5432:5432"
    )
    cmd = " ".join(
        [
            "docker run -d --name pgai-ext --hostname pgai-ext -e POSTGRES_HOST_AUTH_METHOD=trust",
            networking,
            f"--mount type=bind,src={ext_dir()},dst=/pgai",
            "-e TEST_ENV_SECRET=super_secret",
            "pgai-ext",
            "-c shared_preload_libraries='timescaledb, pgextwlist'",
            "-c extwlist.extensions='ai,vector'",
        ]
    )
    subprocess.run(cmd, shell=True, check=True, env=os.environ, text=True)


def docker_stop() -> None:
    subprocess.run(
        """docker stop pgai-ext""", shell=True, check=True, env=os.environ, text=True
    )


def docker_rm() -> None:
    subprocess.run(
        """docker rm --force --volumes pgai-ext""",
        shell=True,
        check=True,
        env=os.environ,
        text=True,
    )


def run() -> None:
    docker_build()
    docker_run()
    cmd = "docker exec pgai-ext make build-install"
    subprocess.run(cmd, shell=True, check=True, env=os.environ, cwd=ext_dir())
    cmd = 'docker exec -u postgres pgai-ext psql -c "create extension ai cascade"'
    subprocess.run(cmd, shell=True, check=True, env=os.environ, cwd=ext_dir())
    cmd = "docker exec -it -d -w /pgai/tests pgai-ext fastapi dev server.py"
    subprocess.run(cmd, shell=True, check=True, env=os.environ, cwd=ext_dir())


if __name__ == "__main__":
    if len(sys.argv) <= 1 or "help" in sys.argv[1:]:
        print(HELP)
        sys.exit(0)
    for action in sys.argv[1:]:
        if action == "install":
            install()
        elif action == "build":
            build()
        elif action == "build-install":
            build_install()
        elif action == "install-prior-py":
            install_prior_py()
        elif action == "install-py":
            install_py()
        elif action == "install-sql":
            install_sql()
        elif action == "freeze":
            freeze()
        elif action == "build-sql":
            build_sql()
        elif action == "clean-sql":
            clean_sql()
        elif action == "clean-py":
            clean_py()
        elif action == "clean":
            clean()
        elif action == "uninstall-py":
            uninstall_py()
        elif action == "uninstall-sql":
            uninstall_sql()
        elif action == "uninstall":
            uninstall()
        elif action == "test-server":
            test_server()
        elif action == "test":
            test()
        elif action == "lint-sql":
            lint_sql()
        elif action == "lint-py":
            lint_py()
        elif action == "lint":
            lint()
        elif action == "format-py":
            format_py()
        elif action == "docker-build":
            docker_build()
        elif action == "docker-run":
            docker_run()
        elif action == "docker-stop":
            docker_stop()
        elif action == "docker-rm":
            docker_rm()
        elif action == "run":
            run()
        else:
            print(f"{action} is not a valid action", file=sys.stderr)
            sys.exit(1)
