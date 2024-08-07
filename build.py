#!/usr/bin/env python3
import os
import subprocess
import shutil
import sys
import tempfile
from pathlib import Path

HELP = """Available targets:
- help              displays this message and exits
- install           installs the project
- uninstall         uninstalls the project
- clean             removes build artifacts from the project directories
- build-sql         constructs the sql files for the extension
- clean-sql         removes sql file artifacts from the project directories
- install-sql       installs the sql files into the postgres installation
- uninstall-sql     removes the sql extension from the postgres installation
- install-prior-py  installs the python package and dependencies from previously released versions
- install-py        installs the python package and dependencies for the current version
- clean-py          removes python build artifacts from the project directories
- uninstall-py      removes the python package and dependencies from the system
- test              runs the unit tests against the docker database
- lint-sql          runs pgspot against the `ai--<this_version>.sql` file
- lint-py           runs ruff linter against the python source files
- lint              runs both sql and python linters
- format-py         runs ruff to check formatting of the python source files
- docker-build      builds the development docker image
- docker-run        launches a container in docker using the docker image
- docker-stop       stops the container
- docker-rm         deletes the development container"""


def versions() -> list[str]:
    return [
        "0.4.0",
        "0.3.0",
        "0.2.0",
        "0.1.0",
    ]  # ADD NEW VERSIONS TO THE FRONT OF THIS LIST! STAY SORTED PLEASE


def this_version() -> str:
    return versions()[0]


def prior_versions() -> list[str]:
    return versions()[1:] if len(versions()) > 1 else []


def project_dir() -> Path:
    return Path(__file__).resolve().absolute().parent


def sql_dir() -> Path:
    return project_dir().joinpath("sql")


def src_dir() -> Path:
    return project_dir().joinpath("src")


def incremental_sql_dir() -> Path:
    return sql_dir().joinpath("incremental")


def idempotent_sql_dir() -> Path:
    return sql_dir().joinpath("idempotent")


def idempotent_sql_files() -> list[Path]:
    paths = [x for x in idempotent_sql_dir().glob("*.sql")]
    paths.sort()
    return paths


def incremental_sql_files() -> list[Path]:
    paths = [x for x in incremental_sql_dir().glob("*.sql")]
    paths.sort()
    return paths


def output_sql_file() -> Path:
    return sql_dir().joinpath(f"ai--{this_version()}.sql")


def build_sql_control_file() -> None:
    ctl_file = sql_dir().joinpath("ai.control")
    content = ctl_file.read_text()
    lines = []
    for line in content.splitlines(keepends=True):
        if line.startswith("default_version"):
            lines.append(f"default_version='{this_version()}'\n")
        else:
            lines.append(line)
    ctl_file.write_text("".join(lines))


def build_incremental_sql_file(input_file: Path) -> str:
    template = sql_dir().joinpath("migration.sql").read_text()
    migration_name = input_file.name
    migration_body = input_file.read_text()
    version = this_version()
    return template.format(
        migration_name=migration_name, migration_body=migration_body, version=version
    )


def build_idempotent_sql_file(input_file: Path) -> str:
    inject = f"""
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '{python_install_dir()}') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
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
    return code.replace(
        """    #ADD-PYTHON-LIB-DIR\n""", inject
    )  # leading 4 spaces is intentional


def build_sql() -> None:
    build_sql_control_file()
    hr = "".rjust(80, "-")
    osf = output_sql_file()
    osf.unlink(missing_ok=True)
    with osf.open("w") as wf:
        wf.write(f"{hr}\n-- {this_version()}\n\n\n")
        with sql_dir().joinpath("head.sql").open("r") as rf:
            shutil.copyfileobj(rf, wf)
        wf.write("\n\n\n")
        for inc_file in incremental_sql_files():
            code = build_incremental_sql_file(inc_file)
            wf.write(code)
            wf.write("\n\n\n")
        for idm_file in idempotent_sql_files():
            wf.write(f"{hr}\n-- {idm_file.name}\n")
            wf.write(build_idempotent_sql_file(idm_file))
            wf.write("\n\n\n")
        wf.flush()
        wf.close()
    for prior_version in prior_versions():
        if prior_version in {
            "0.3.0",
            "0.2.0",
            "0.1.0",
        }:  # we don't allow upgrades from these versions
            continue
        dest = sql_dir().joinpath(f"ai--{prior_version}--{this_version()}.sql")
        dest.unlink(missing_ok=True)
        shutil.copyfile(osf, dest)


def clean_sql() -> None:
    for f in sql_dir().glob(f"ai--*.*.*--{this_version()}.sql"):
        f.unlink()
    sql_dir().joinpath(f"ai--{this_version()}.sql").unlink()


def extension_dir() -> Path:
    if shutil.which("pg_config") is None:
        print("pg_config not found", file=sys.stderr)
        sys.exit(1)
    proc = subprocess.run(
        "pg_config --sharedir",
        check=True,
        shell=True,
        env=os.environ,
        text=True,
        capture_output=True,
    )
    return Path(str(proc.stdout).strip()).resolve().absolute().joinpath("extension")


def install_sql() -> None:
    ext_dir = extension_dir()
    if not ext_dir.exists():
        print(f"extension directory does not exist: {ext_dir}", file=sys.stderr)
        sys.exit(1)
    build_sql()
    for src in sql_dir().glob("ai*.control"):
        dest = ext_dir.joinpath(src.name)
        shutil.copyfile(src, dest)
    for src in sql_dir().glob("ai--*.sql"):
        dest = ext_dir.joinpath(src.name)
        shutil.copyfile(src, dest)


def uninstall_sql() -> None:
    ext_dir = extension_dir()
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
    return (
        Path("/usr/local/lib/pgai").resolve().absolute()
    )  # CONTROLS WHERE THE PYTHON LIB AND DEPS ARE INSTALLED


def install_old_py_deps() -> None:
    # this is necessary for versions prior to 0.4.0
    # we will deprecate these versions and then get rid of this function
    old_reqs_file = src_dir().joinpath("old_requirements.txt")
    if old_reqs_file.exists():
        env = {k: v for k, v in os.environ.items()}
        env["PIP_BREAK_SYSTEM_PACKAGES"] = "1"
        subprocess.run(
            f"pip install --compile -r {old_reqs_file}", shell=True, check=True, env=env
        )


def install_prior_py() -> None:
    install_old_py_deps()
    for version in prior_versions():
        if version in {
            "0.3.0",
            "0.2.0",
            "0.1.0",
        }:  # these are handled by install_old_py_deps()
            continue
        if os.sep in version:
            print(
                f"'{os.sep}' in version {version}. this is not supported",
                file=sys.stderr,
            )
            sys.exit(1)
        version_target_dir = python_install_dir().joinpath(version)
        if version_target_dir.exists():
            continue
        tmp_dir = Path(tempfile.gettempdir()).joinpath("pgai", version)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            f"git clone https://github.com/timescale/pgai.git --branch {version} {tmp_dir}",
            shell=True,
            check=True,
            env=os.environ,
        )
        tmp_src_dir = tmp_dir.joinpath("src")
        subprocess.run(
            f'pip install --compile -t "{version_target_dir}" "{tmp_src_dir}"',
            check=True,
            shell=True,
            env=os.environ,
        )
        shutil.rmtree(tmp_dir)


def build_pyproject_toml() -> None:
    # pyproject.toml is checked in to version control. So, all the previous
    # versions will have the file with the correct version already in it. This
    # function just ensures that you can't screw up the current version. The
    # only place you have to update the version when starting a new release is
    # in the versions() function.
    prj_file = src_dir().joinpath("pyproject.toml")
    content = prj_file.read_text()
    lines = []
    for line in content.splitlines(keepends=True):
        if line.startswith("version"):
            lines.append(f'version = "{this_version()}"\n')
        else:
            lines.append(line)
    prj_file.write_text("".join(lines))


def install_py() -> None:
    build_pyproject_toml()
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
        subprocess.run(
            f'pip install --no-deps --compile -t "{version_target_dir}" "{src_dir()}"',
            check=True,
            shell=True,
            env=os.environ,
        )
    else:
        version_target_dir.mkdir(exist_ok=True)
        subprocess.run(
            f'pip install --compile -t "{version_target_dir}" "{src_dir()}"',
            check=True,
            shell=True,
            env=os.environ,
        )


def clean_py() -> None:
    d = src_dir().joinpath("build")
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    d = src_dir().joinpath("pgai.egg-info")
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def uninstall_py() -> None:
    shutil.rmtree(python_install_dir(), ignore_errors=True)


def uninstall() -> None:
    uninstall_sql()
    uninstall_py()


def install() -> None:
    install_prior_py()
    install_py()
    install_sql()


def clean() -> None:
    clean_sql()
    clean_py()


def test() -> None:
    subprocess.run("pytest", shell=True, check=True, env=os.environ, cwd=project_dir())


def lint_sql() -> None:
    sql = sql_dir().joinpath(f"ai--{this_version()}.sql")
    subprocess.run(
        f"pgspot --ignore-lang=plpython3u {sql}", shell=True, check=True, env=os.environ
    )


def lint_py() -> None:
    subprocess.run(f"ruff check {src_dir()}", shell=True, check=True, env=os.environ)


def lint() -> None:
    lint_py()
    lint_sql()


def format_py() -> None:
    subprocess.run(
        f"ruff format --diff {src_dir()}", shell=True, check=True, env=os.environ
    )


def docker_build() -> None:
    assert Path.cwd() == project_dir()
    subprocess.run(
        """docker build -t pgai .""", shell=True, check=True, env=os.environ, text=True
    )


def docker_run() -> None:
    cmd = f"""docker run -d --name pgai -p 127.0.0.1:9876:5432 -e POSTGRES_HOST_AUTH_METHOD=trust --mount type=bind,src={project_dir()},dst=/pgai pgai"""
    subprocess.run(cmd, shell=True, check=True, env=os.environ, text=True)


def docker_stop() -> None:
    subprocess.run(
        """docker stop pgai""", shell=True, check=True, env=os.environ, text=True
    )


def docker_rm() -> None:
    subprocess.run(
        """docker rm pgai""", shell=True, check=True, env=os.environ, text=True
    )


if __name__ == "__main__":
    if len(sys.argv) <= 1 or "help" in sys.argv[1:]:
        print(HELP)
        sys.exit(0)
    for action in sys.argv[1:]:
        if action == "install":
            install()
        elif action == "install-prior-py":
            install_prior_py()
        elif action == "install-py":
            install_py()
        elif action == "install-sql":
            install_sql()
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
        else:
            print(f"{action} is not a valid action", file=sys.stderr)
            sys.exit(1)
