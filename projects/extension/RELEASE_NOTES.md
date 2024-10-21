
# Pgai Extension Release Notes

# pgai extension 0.4.0 (2024-10-23)

This release adds the [Vectorizer](/docs/vectorizer.md) feature to the extension. Vectorizer is an 
innovative SQL-level interface for automating the embedding process within
the database. Vectorizer treats embeddings as a declarative, DDL-like feature, similar to 
an index. For more details, check out the [documentation](/docs/vectorizer.md).

### Breaking changes

- There are no update paths from 0.1.0, 0.2.0, 0.3.0 to the 0.4.0 release. You 
  must `DROP EXTENSION ai` and then `CREATE EXTENSION ai VERSION '0.4.0' CASCADE`.
- The pgai extension is now installed in the `ai` schema. It was previously 
  installed in the `public` schema by default, but could be explicitly put in 
  another schema. All pgai functions have moved to the `ai` schema. For example,
  `openai_list_models()` is now `ai.openai_list_models()`
- The `pg_database_owner` and the database user running `CREATE EXTENSION` now get
  admin privileges over the extension. Other database users and roles need to
  be granted privileges to use the extension. You do this using [functions](docs/privileges.md).

### New features and improvements

- Added the Vectorizer feature.
- Added support for the `rank_fields` parameter to the `cohere_rerank` function.
- Added support for the `base_url` parameter to the OpenAI functions.
- Various functions were changed from `volatile` to `immutable` for performance.
- Added `ai.openai_chat_complete_simple` function.


