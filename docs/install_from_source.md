# Install the pgai extension from source

To install pgai from source on a PostgreSQL server:

1. **Install the prerequisite software system-wide**

   - **PostgreSQL**: Version 16 or newer is required.

   - **Python3**: if running `python3 --version` in Terminal returns `command
     not found`, download and install the latest version of [Python3][python3].

   - **Pip**: if running `pip --version` in Terminal returns `command not found`, install it with one of the pip [supported methods][pip].

   - **PL/Python**: follow [How to install Postgres 16 with plpython3u: Recipes for macOS, Ubuntu, Debian, CentOS, Docker][pgai-plpython].

      _macOS_: the standard PostgreSQL brew in Homebrew does not include the `plpython3` extension. These instructions show
      how to install from an alternate tap.

     - **[Postgresql plugin][asdf-postgres] for the [asdf][asdf] version manager**: set the `--with-python` option
       when installing PostgreSQL:

       ```bash
       POSTGRES_EXTRA_CONFIGURE_OPTIONS=--with-python asdf install postgres 16.3
       ```

   - **pgvector**: follow the [install instructions][pgvector-install] from the official repository. This extension is automatically added to your PostgreSQL database when you install the pgai extension.


1. Clone the pgai repo at the latest tagged release:

    ```bash
    git clone https://github.com/timescale/pgai.git --branch extension-0.6.0
    cd pgai
    ```

1. Install the `pgai` PostgreSQL extension:

    ```bash
    just ext install
    ```
    We use [just][just] to run project commands. If you don't have just you can
    install the extension with:

    ```bash
    projects/extension/build.py install
    ```

1. Connect to your database with a postgres client like [psql v16](https://docs.timescale.com/use-timescale/latest/integrations/query-admin/psql/)
   or [PopSQL](https://docs.timescale.com/use-timescale/latest/popsql/).
   ```bash
   psql -d "postgres://<username>:<password>@<host>:<port>/<database-name>"
   ```

1. Create the pgai extension:

    ```sql
    CREATE EXTENSION IF NOT EXISTS ai CASCADE;
    ```

   The `CASCADE` automatically installs `pgvector` and `plpython3u` extensions.

[pgai-plpython]: https://github.com/postgres-ai/postgres-howtos/blob/main/0047_how_to_install_postgres_16_with_plpython3u.md
[asdf-postgres]: https://github.com/smashedtoatoms/asdf-postgres
[asdf]: https://github.com/asdf-vm/asdf
[python3]: https://www.python.org/downloads/
[pip]: https://pip.pypa.io/en/stable/installation/#supported-methods
[plpython3u]: https://www.postgresql.org/docs/current/plpython.html
[pgvector]: https://github.com/pgvector/pgvector
[pgvector-install]: https://github.com/pgvector/pgvector?tab=readme-ov-file#installation
[python-virtual-environment]: https://packaging.python.org/en/latest/tutorials/installing-packages/#creating-and-using-virtual-environments
[create-a-new-service]: https://console.cloud.timescale.com/dashboard/create_services
[just]: https://github.com/casey/just
