Previous versions of pgai vectorizer used an extension to provide the vectorizer
functionality.  We have removed the need for the extension and put the
vectorizer code into the pgai python library. This change allows the vectorizer
to be used on more PostgreSQL cloud providers (AWS RDS, Supabase, etc.) and
simplifies the installation and upgrade process.

Versions that used the extension:
- `ai` extension version < 0.10.0
- `pgai` python library version < 0.10.0

# Migrating from the extension to the python library

We made this change in a way that will allow current users of the vectorizer to
continue using the feature without interruption, but they will have to modify how they
upgrade vectorizer functionality in the future.

The upgrade process is as follows:

1. **Upgrade the extension:** Run ALTER EXTENSION ai UPDATE TO '0.10.0' to detach the vectorizer catalog tables and functions from the extension. This leaves them in your database in the ai schema, and the vectorizer will continue to work.
2. **Upgrade the pgai python library:** Upgrade the pgai Python library to version `>0.10.0`. This can be done with `pip install -U pgai` or via your `requirements.txt` or similar dependency file.
3. **Manage the vectorizer with the python library:** You can then manage the vectorizer from the python library or cli by using `pgai install -d DB_URL` as described in the new python-library-based [workflow](/docs/vectorizer/api-reference.md#install-or-upgrade-the-database-objects-necessary-for-vectorizer).
3. **(Optional) Remove the extension:** If you are not using Timescale Cloud and you don't use the model calling capabilities of pgai, you can then remove the pgai extension from your database.

> [!WARNING]
> If you are using Timescale Cloud, you will need to keep the extension installed to use the vectorizer cloud functions.

# Changes to the `create_vectorizer` API.

During the transition to the python library, some APIs changed for the `ai.create_vectorizer` call. On a high level:
-  The `ai.create_vectorizer` call now requires a top-level `loading` argument. This allows us more flexibility in how we load data into the vectorizer. For example, we can now load data from file using the [`loading => loading_uri()`](/docs/vectorizer/api-reference.md#ailoading_uri) function.
- The destination where embeddings are stored is now configured via the `destination` top-level argument. This was done to allow us to support more types of schema design for storing embeddings. For example, we can now store embeddings in a column of a table via the [`destination => ai.destination_column()`](/docs/vectorizer/api-reference.md#aidestination_column) function in addition to the previous behavior of using a separate table via the [`destination => ai.destination_table()`](/docs/vectorizer/api-reference.md#aidestination_table) function.

These changes are automatically applied to existing vectorizers. But, when creating new vectorizers, developers should be aware of the following changes:

* `ai.create_vectorizer` now requires a [`loading =>`](https://github.com/timescale/pgai/blob/main/docs/vectorizer/api-reference.md#loading-configuration) argument. Previous behavior is provided via the [`loading => loading_column()`](https://github.com/timescale/pgai/blob/main/docs/vectorizer/api-reference.md#ailoading_column) function.
* `ai.create_vectorizer` no longer takes `destination`, `target_table`, `target_schema`, `view_schema`, `view_name` as arguments configure these options via the new [`destination => ai.destination_table()`](https://github.com/timescale/pgai/blob/main/docs/vectorizer/api-reference.md#destination-configuration) function instead.
* [ai.chunking_character_text_splitter](https://github.com/timescale/pgai/blob/main/docs/vectorizer/api-reference.md#aichunking_character_text_splitter) and [ai.chunking_recursive_character_text_splitter](https://github.com/timescale/pgai/blob/main/docs/vectorizer/api-reference.md#aichunking_recursive_character_text_splitter) no longer take a `chunk_column` argument, that column name is now provided via [`loading => loading_column()`](https://github.com/timescale/pgai/blob/main/docs/vectorizer/api-reference.md#ailoading_column) function instead.
