
# Pgai extension release notes

## 0.6.0 (2024-12-10)

This release adds support for using Voyage AI in a vectorizer, and loading
datasets from hugging face.

### New features and improvements

- Use the `ai.voyageai_embed`, and `ai.embedding_voyageai` functions to use Voyage AI for vector embeddings 1b56d62295faf996697db75f3a9ac9391869a3bb.
- Add `ai.load_dataset` to load datasets from hugging face 29469388f22d15ae79e293f8151ef0a730820b3c.
- Change the type of `keep_alive` parameter from `float8` to `text` 0c747418efc70d656330f605195bf0d2c164bec2
- Remove `truncate` parameter from Ollama/Voyage APIs ecda03cf5d27f750db534801719413d0abcfa557

### Fixes

- Fix Anthropic tool use 2cb2fe9c55f44da82e605a47194428a11f77f9de.

## 0.5.0 (2024-11-26)

This release adds support for using Ollama in a vectorizer, and fixes a bug
introduced in 0.4.1.

### New features and improvements

- Use the `ai.embedding_ollama` function to configure a vectorizer to use an Ollama API 6a4a449e99e2e5e62b5f551206a0b28e5ad40802.

### Fixes

- Allow members of source table to create vectorizer 39537792048b64049b252ee11f1236b906e0b726.

## 0.4.1 (2024-11-19)

This release focuses on improving reliability, performance, and maintainability 
while fixing several important edge cases in table management and permissions.

### New features and improvements

- Various improvements to build tooling
- Based on prior benchmarking, using storage plain (rather than extended/external) for vector columns
  performs much better. Unfortunately, it is difficult to determine whether a target table row will
  definitively fit on a single postgres page. Therefore, we will assign storage main to the vector
  columns, which will keep them inline unless they won't fit and toast otherwise.
  NOTE: We will set storage to main for existing vectorizers (unless they have been already manually
  set to main or plain), but this will not take effect until a table rewrite happens. This can be
  done with `CLUSTER` or `VACUUM FULL` and may take a while depending on the size of the table.
  c64f2403219788a42d981b3ee299530bbd9a94e4
- Dropping the source table with cascade will drop the target too 644858dd685f897ba28f509562773f1d475f1b9e
- Added entries into pg_depend such that when you `drop table <source-table> cascade` or
  `drop table <target-table> cascade` it will also drop the queue table for 
  vectorizers. f68e73ac5e82f41b4bcd25a0976daef889b34d1f
- Created a more thorough snapshot in upgrade tests 2b330a4ea732ef94d00808a24d96c43c846dfa6b
- Added a vectorizer and secret to upgrade tests a1d4104cf798de84a85189aaccf3a0af9bc17b93
- Added a test to ensure ai.secret_permissions is dumped/restored properly. 5a9bfd1fb1b415c38e2a60430dac9762cb59de5a
- Added cache for secrets 20809c16745540bd8bc21a546f0d0b7ec912549e
- Allowed drop_vectorizer to optionally drop target and view ec53befe9151a2d0091de53ace068b8ea2f12573
- Added an api_key_name parameter to allow functions to remain immutable while 
  getting a secret. This avoids having to use ai.reveal_secret() which is stable 
  and not immutable. This allows for more efficient queries when getting a secret 
  that is not the one with a default query. 59b86d66f92840eed49f80e9ebdcf4f0c60475bd
- Made reveal_secrets stable f2e0e1489f2ac30f824db7ff137e1252463bddb1
- Added an event trigger to detect when a source, queue, or target table associated 
  with a vectorizer is dropped. The event trigger calls ai.drop_vectorizer to 
  clean up the mess. a01e6208e81942b289970feebfc96bafb95c3fcc
- Allowed SQL to be gated behind feature flags. This commit added support for building 
  and shipping prerelease SQL code gated behind feature flags in extension versions 
  that include a prerelease tag. Prerelease SQL code is omitted entirely from 
  extension versions that do not include a prerelease tag. For details, see 
  DEVELOPMENT.md d2bcbfaa83f424d9b8d6894d4d206be8f84ab8d6
- Added tests to check that extension upgrades work d2bcbfaa83f424d9b8d6894d4d206be8f84ab8d6

### Fixes

- Made ai.secret_permissions dump/restore properly. Two rows are inserted into 
  ai.secret_permissions on extension creation. If these rows are dumped, then on 
  restore the extension creation inserts them AND the table restoration tries to insert them.
  This causes a constraint violation and prevents the table from restoring properly.
  This commit added a filter to prevent the two rows from being dumped. 39d61db97e85f61441dbe2eafa2bee209bc797fd
- Prevent vectorizer status view from failing if missing privileges to one or more
  vectorizer queue tables 44ea1cb0f92b294284ae252fd179191d83145d5c
- Handle dropped columns when creating vectorizers 814f0ba5a27d69f839c7c8232b118a7a4d0e6772
- Avoid inserting duplicates into ai._secret_permissions. This fixes an issue that
  would cause upgrade to fail. ec2363a9f55cc25ce1295526c9f90d9446edd97b

### Breaking changes

- Previously, the vectorizer_queue_pending function would return an exact count which could be very
  slow for queues with a large number of rows. Now, by default, we limit the count to 10000 by
  default. An `exact_count` parameter was added. If true, the original behavior is used. 
  c11db9c2d7fb8346f28f4de17bf3706e9d1620d4
- If a vectorizer has no queue table, or the user does not have select privileges on the queue table
  we will now return null for the pending_items column in the vectorizer_status view. 
  f17d1b908df9fd7072b5554de7dc162102a5611b

### Deprecations

- Versions `0.1.0`, `0.2.0`, and `0.3.0` are deprecated and will be removed in a future release.
  To upgrade from a deprecated version, you must `DROP EXTENSION ai` and then `CREATE EXTENSION ai VERSION '0.4.1' CASCADE`.

## 0.4.0 (2024-10-23)

This release adds the [Vectorizer](/docs/vectorizer.md) feature to the extension. Vectorizer is an 
innovative SQL-level interface for automating the embedding process within
the database. Vectorizer treats embeddings as a declarative, DDL-like feature, similar to 
an index. For more details, check out the [documentation](/docs/vectorizer.md).

### New features and improvements

- Added the Vectorizer feature.
- Added support for the `rank_fields` parameter to the `cohere_rerank` function.
- Added support for the `base_url` parameter to the OpenAI functions.
- Various functions were changed from `volatile` to `immutable` for performance.
- Added `ai.openai_chat_complete_simple` function.

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
- The parameter names to the openai*, ollama*, anthropic*, and cohere* functions
  were renamed to remove underscore prefixes and conflicts with reserved and
  non-reserved keywords.


