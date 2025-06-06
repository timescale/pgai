<a id="pgai.semantic_catalog.describe"></a>

# pgai.semantic\_catalog.describe

Module for generating descriptions of database objects using AI.

This module provides functionality for finding database objects (tables, views, procedures)
and generating natural language descriptions for them using AI models. These descriptions
can be used to populate a semantic catalog, making it easier for users to understand
the database schema and its purpose.

<a id="pgai.semantic_catalog.describe.find_tables"></a>

#### find\_tables

```python
async def find_tables(
        con: TargetConnection,
        include_schema: str | None = None,
        exclude_schema: str | None = None,
        include_table: str | None = None,
        exclude_table: str | None = None,
        include_extensions: list[str] | None = None) -> list[int]
```

Find PostgreSQL tables matching specified criteria.

Searches the database for tables that match the specified inclusion/exclusion patterns
for schemas and table names. System schemas and TimescaleDB internal schemas are excluded.
Regular, foreign, and partitioned tables are included.

**Arguments**:

- `con` - Database connection to use for the search.
- `include_schema` - Regular expression pattern for schemas to include (optional).
- `exclude_schema` - Regular expression pattern for schemas to exclude (optional).
- `include_table` - Regular expression pattern for tables to include (optional).
- `exclude_table` - Regular expression pattern for tables to exclude (optional).
  

**Returns**:

  A list of PostgreSQL object IDs (OIDs) for the matching tables.

<a id="pgai.semantic_catalog.describe.find_views"></a>

#### find\_views

```python
async def find_views(con: TargetConnection,
                     include_schema: str | None = None,
                     exclude_schema: str | None = None,
                     include_view: str | None = None,
                     exclude_view: str | None = None,
                     include_extensions: list[str] | None = None) -> list[int]
```

Find PostgreSQL views matching specified criteria.

Searches the database for views that match the specified inclusion/exclusion patterns
for schemas and view names. System schemas and TimescaleDB internal schemas are excluded.
Regular and materialized views are included.

**Arguments**:

- `con` - Database connection to use for the search.
- `include_schema` - Regular expression pattern for schemas to include (optional).
- `exclude_schema` - Regular expression pattern for schemas to exclude (optional).
- `include_view` - Regular expression pattern for views to include (optional).
- `exclude_view` - Regular expression pattern for views to exclude (optional).
  

**Returns**:

  A list of PostgreSQL object IDs (OIDs) for the matching views.

<a id="pgai.semantic_catalog.describe.find_procedures"></a>

#### find\_procedures

```python
async def find_procedures(
        con: TargetConnection,
        include_schema: str | None = None,
        exclude_schema: str | None = None,
        include_proc: str | None = None,
        exclude_proc: str | None = None,
        include_extensions: list[str] | None = None) -> list[int]
```

Find PostgreSQL procedures and functions matching specified criteria.

Searches the database for procedures and functions that match the specified
inclusion/exclusion patterns for schemas and procedure/function names.
System schemas and TimescaleDB internal schemas are excluded.

**Arguments**:

- `con` - Database connection to use for the search.
- `include_schema` - Regular expression pattern for schemas to include (optional).
- `exclude_schema` - Regular expression pattern for schemas to exclude (optional).
- `include_proc` - Regular expression pattern for procedures/functions to include (optional).
- `exclude_proc` - Regular expression pattern for procedures/functions to exclude (optional).
  

**Returns**:

  A list of PostgreSQL object IDs (OIDs) for the matching procedures and functions.

<a id="pgai.semantic_catalog.describe.generate_table_descriptions"></a>

#### generate\_table\_descriptions

```python
async def generate_table_descriptions(con: TargetConnection,
                                      oids: list[int],
                                      model: KnownModelName | Model,
                                      callback: Callable[[file.Table], None],
                                      progress_callback: Callable[[str], None]
                                      | None = None,
                                      usage: Usage | None = None,
                                      usage_limits: UsageLimits | None = None,
                                      model_settings: ModelSettings
                                      | None = None,
                                      batch_size: int = 5,
                                      sample_size: int = 3) -> Usage
```

Generate natural language descriptions for tables and their columns using AI.

Retrieves table metadata from the database in batches, renders it, and uses an AI model
to generate concise descriptions for each table and column. The descriptions are provided
to the callback function as they are generated.

**Arguments**:

- `con` - Database connection to use for loading table metadata.
- `oids` - List of PostgreSQL object IDs for the tables to describe.
- `model` - AI model to use for generating descriptions.
- `callback` - Function to call with each generated table description.
- `progress_callback` - Optional function to call with progress updates.
- `usage` - Optional Usage object to track API usage across multiple calls.
- `usage_limits` - Optional UsageLimits object to set limits on API usage.
- `model_settings` - Optional settings for the AI model.
- `batch_size` - Number of tables to process in each batch (default: 5).
- `sample_size` - Number of sample rows to include for each table (default: 3).
  

**Returns**:

  Updated Usage object with information about token usage.

<a id="pgai.semantic_catalog.describe.generate_view_descriptions"></a>

#### generate\_view\_descriptions

```python
async def generate_view_descriptions(con: TargetConnection,
                                     oids: list[int],
                                     model: KnownModelName | Model,
                                     callback: Callable[[file.View], None],
                                     progress_callback: Callable[[str], None]
                                     | None = None,
                                     usage: Usage | None = None,
                                     usage_limits: UsageLimits | None = None,
                                     model_settings: ModelSettings
                                     | None = None,
                                     batch_size: int = 5,
                                     sample_size: int = 3) -> Usage
```

Generate natural language descriptions for views and their columns using AI.

Retrieves view metadata from the database in batches, renders it, and uses an AI model
to generate concise descriptions for each view and column. The descriptions are provided
to the callback function as they are generated.

**Arguments**:

- `con` - Database connection to use for loading view metadata.
- `oids` - List of PostgreSQL object IDs for the views to describe.
- `model` - AI model to use for generating descriptions.
- `callback` - Function to call with each generated view description.
- `progress_callback` - Optional function to call with progress updates.
- `usage` - Optional Usage object to track API usage across multiple calls.
- `usage_limits` - Optional UsageLimits object to set limits on API usage.
- `model_settings` - Optional settings for the AI model.
- `batch_size` - Number of views to process in each batch (default: 5).
- `sample_size` - Number of sample rows to include for each view (default: 3).
  

**Returns**:

  Updated Usage object with information about token usage.

<a id="pgai.semantic_catalog.describe.generate_procedure_descriptions"></a>

#### generate\_procedure\_descriptions

```python
async def generate_procedure_descriptions(
        con: TargetConnection,
        oids: list[int],
        model: KnownModelName | Model,
        callback: Callable[[file.Function | file.Procedure | file.Aggregate],
                           None],
        progress_callback: Callable[[str], None] | None = None,
        usage: Usage | None = None,
        usage_limits: UsageLimits | None = None,
        model_settings: ModelSettings | None = None,
        batch_size: int = 5) -> Usage
```

Generate natural language descriptions for procedures and functions using AI.

Retrieves procedure/function metadata from the database in batches, renders it, and uses
an AI model to generate concise descriptions. The descriptions are provided
to the callback function as they are generated. Supports procedures, functions, and aggregates.

**Arguments**:

- `con` - Database connection to use for loading procedure metadata.
- `oids` - List of PostgreSQL object IDs for the procedures to describe.
- `model` - AI model to use for generating descriptions.
- `callback` - Function to call with each generated procedure description.
- `progress_callback` - Optional function to call with progress updates.
- `usage` - Optional Usage object to track API usage across multiple calls.
- `usage_limits` - Optional UsageLimits object to set limits on API usage.
- `model_settings` - Optional settings for the AI model.
- `batch_size` - Number of procedures to process in each batch (default: 5).
  

**Returns**:

  Updated Usage object with information about token usage.

<a id="pgai.semantic_catalog.describe.describe"></a>

#### describe

```python
async def describe(db_url: str,
                   model: KnownModelName | Model,
                   output: TextIO,
                   console: Console | None = None,
                   include_schema: str | None = None,
                   exclude_schema: str | None = None,
                   include_table: str | None = None,
                   exclude_table: str | None = None,
                   include_view: str | None = None,
                   exclude_view: str | None = None,
                   include_proc: str | None = None,
                   exclude_proc: str | None = None,
                   include_extensions: list[str] | None = None,
                   usage: Usage | None = None,
                   usage_limits: UsageLimits | None = None,
                   batch_size: int = 5,
                   sample_size: int = 3,
                   dry_run: bool = False) -> Usage
```

Generate natural language descriptions for database objects and export them to YAML.

This is the main entry point for the describe functionality. It finds database objects
matching the specified criteria, generates descriptions for them using AI, and writes
the results to the output file in YAML format. Progress is tracked and displayed using
the rich console.

**Arguments**:

- `db_url` - Database connection URL.
- `model` - AI model to use for generating descriptions.
- `output` - Text output stream to write the YAML data to.
- `console` - Optional Rich console for displaying progress and messages.
- `include_schema` - Regular expression pattern for schemas to include (optional).
- `exclude_schema` - Regular expression pattern for schemas to exclude (optional).
- `include_table` - Regular expression pattern for tables to include (optional).
- `exclude_table` - Regular expression pattern for tables to exclude (optional).
- `include_view` - Regular expression pattern for views to include (optional).
- `exclude_view` - Regular expression pattern for views to exclude (optional).
- `include_proc` - Regular expression pattern for procedures to include (optional).
- `exclude_proc` - Regular expression pattern for procedures to exclude (optional).
- `usage` - Optional Usage object to track API usage across multiple calls.
- `usage_limits` - Optional UsageLimits object to set limits on API usage.
- `batch_size` - Number of objects to process in each batch (default: 5).
- `sample_size` - Number of sample rows to include for tables and views (default: 3).
  

**Returns**:

  Updated Usage object with information about token usage.

<a id="pgai.semantic_catalog.models"></a>

# pgai.semantic\_catalog.models

<a id="pgai.semantic_catalog.models.ObjectDescription"></a>

## ObjectDescription Objects

```python
class ObjectDescription(BaseModel)
```

Model representing a description of a database object.

This class represents the metadata and description of database objects such as
tables, views, functions, etc. It includes identifiers that can be used to
locate the object in the database, as well as a textual description.

**Attributes**:

- `id` - Semantic catalog ID (default: -1 if not assigned).
- `classid` - PostgreSQL object class ID (for pg_class, pg_proc, etc.).
- `objid` - PostgreSQL object ID within its class.
- `objsubid` - PostgreSQL sub-object ID (e.g., column number).
- `objtype` - Type of object (table, view, function, etc.).
- `objnames` - Object name components (schema, name, etc.).
- `objargs` - Object argument types for procedures/functions.
- `description` - Textual description of the object.

<a id="pgai.semantic_catalog.models.Column"></a>

## Column Objects

```python
class Column(BaseModel)
```

Model representing a database column.

This class represents a column in a database table or view, including its
data type, constraints, and description.

**Attributes**:

- `classid` - PostgreSQL object class ID for the parent table/view.
- `objid` - PostgreSQL object ID of the parent table/view.
- `objsubid` - PostgreSQL sub-object ID (column number).
- `name` - Column name.
- `type` - PostgreSQL data type of the column.
- `is_not_null` - Boolean indicating if the column has a NOT NULL constraint.
- `default_value` - Default value expression for the column (if any).
- `description` - Object description containing metadata and textual description.

<a id="pgai.semantic_catalog.models.Dimension"></a>

## Dimension Objects

```python
class Dimension(BaseModel)
```

Model representing a dimension in a TimescaleDB hypertable.

This class represents a partitioning dimension in a TimescaleDB hypertable,
which can be time-based or space-based.

**Attributes**:

- `column_name` - Name of the column used for partitioning.
- `dimension_builder` - Type of partitioning strategy (by_range, by_hash).
- `partition_func` - Custom partitioning function (if any).
- `partition_interval` - Time interval for time-based partitioning.
- `number_partitions` - Number of partitions for hash partitioning.

<a id="pgai.semantic_catalog.models.View"></a>

## View Objects

```python
class View(BaseModel)
```

Model representing a database view.

This class represents a view in a database, which can be a regular view,
materialized view, or a TimescaleDB continuous aggregate view.

**Attributes**:

- `id` - Semantic catalog ID (default: -1 if not assigned).
- `classid` - PostgreSQL object class ID.
- `objid` - PostgreSQL object ID.
- `schema_name` - Schema name where the view is defined.
- `view_name` - Name of the view.
- `is_materialized` - Boolean indicating if the view is materialized.
- `is_continuous_aggregate` - Boolean indicating if the view is a TimescaleDB continuous aggregate.
- `columns` - List of columns in the view.
- `definition` - SQL definition of the view.
- `description` - Object description containing metadata and textual description.
- `sample` - Sample data from the view (if available).

<a id="pgai.semantic_catalog.models.Procedure"></a>

## Procedure Objects

```python
class Procedure(BaseModel)
```

Model representing a database procedure, function, or aggregate.

This class represents a callable database object, which can be a procedure,
function, or aggregate function.

**Attributes**:

- `id` - Semantic catalog ID (default: -1 if not assigned).
- `classid` - PostgreSQL object class ID.
- `objid` - PostgreSQL object ID.
- `schema_name` - Schema name where the procedure is defined.
- `proc_name` - Name of the procedure.
- `kind` - Type of procedure ("procedure", "function", or "aggregate").
- `identity_args` - String representation of the argument types for identification.
- `definition` - SQL definition of the procedure.
- `objargs` - List of argument types as strings.
- `description` - Object description containing metadata and textual description.

<a id="pgai.semantic_catalog.models.Constraint"></a>

## Constraint Objects

```python
class Constraint(BaseModel)
```

Model representing a database constraint.

This class represents a constraint in a database table, such as primary key,
foreign key, unique, or check constraints.

**Attributes**:

- `name` - Name of the constraint.
- `definition` - SQL definition of the constraint.

<a id="pgai.semantic_catalog.models.Index"></a>

## Index Objects

```python
class Index(BaseModel)
```

Model representing a database index.

This class represents an index on a database table.

**Attributes**:

- `name` - Name of the index.
- `definition` - SQL definition of the index.

<a id="pgai.semantic_catalog.models.Table"></a>

## Table Objects

```python
class Table(BaseModel)
```

Model representing a database table.

This class represents a table in a database, including its columns, constraints,
indexes, and potentially TimescaleDB hypertable dimensions.

**Attributes**:

- `id` - Semantic catalog ID (default: -1 if not assigned).
- `classid` - PostgreSQL object class ID.
- `objid` - PostgreSQL object ID.
- `schema_name` - Schema name where the table is defined.
- `table_name` - Name of the table.
- `persistence` - Table persistence type ("temporary" or "unlogged") if applicable.
- `columns` - List of columns in the table.
- `constraints` - List of constraints on the table.
- `indexes` - List of indexes on the table.
- `dimensions` - List of TimescaleDB dimensions if the table is a hypertable.
- `description` - Object description containing metadata and textual description.
- `sample` - Sample data from the table (if available).

<a id="pgai.semantic_catalog.models.SQLExample"></a>

## SQLExample Objects

```python
class SQLExample(BaseModel)
```

Model representing an example SQL query.

This class represents an example SQL query with a description of what it does.
These examples can be used to help users understand how to query the database.

**Attributes**:

- `id` - Semantic catalog ID (default: -1 if not assigned).
- `sql` - The SQL query text.
- `description` - Description of what the SQL query does.

<a id="pgai.semantic_catalog.models.Fact"></a>

## Fact Objects

```python
class Fact(BaseModel)
```

Model representing a fact about the database or domain.

This class represents a descriptive fact about the database, its schema,
or the business domain it models. These facts can provide context and information
that isn't captured in the specific database object descriptions.

**Attributes**:

- `id` - Semantic catalog ID (default: -1 if not assigned).
- `description` - The text of the fact.

<a id="pgai.semantic_catalog.vectorizer.models"></a>

# pgai.semantic\_catalog.vectorizer.models

Models for representing data being vectorized in the semantic catalog.

This module contains the data models used for representing content that will be
converted to vector embeddings for the semantic catalog.

<a id="pgai.semantic_catalog.vectorizer.models.EmbedRow"></a>

## EmbedRow Objects

```python
class EmbedRow(BaseModel)
```

Model representing a row of data to be embedded.

This class holds the content to be embedded and its resulting vector embedding.
It serves as the data structure for passing content to embedding services and
storing the resulting vector embeddings.

**Attributes**:

- `id` - Database ID of the item being embedded.
- `content` - Text content to be converted to a vector embedding.
- `vector` - The resulting vector embedding (None until embedding is performed).

<a id="pgai.semantic_catalog.vectorizer.sentence_tranformers"></a>

# pgai.semantic\_catalog.vectorizer.sentence\_tranformers

SentenceTransformers embedding provider for the semantic catalog vectorizer.

This module implements embedding functionality using SentenceTransformers as the
embedding provider. It provides functions for embedding both batches of content and
individual queries.

<a id="pgai.semantic_catalog.vectorizer.sentence_tranformers.disable_logging"></a>

#### disable\_logging

```python
@contextmanager
def disable_logging()
```

Disable logging for the sentence_transformers and transformers_modules
libraries.

<a id="pgai.semantic_catalog.vectorizer.sentence_tranformers.embed_batch"></a>

#### embed\_batch

```python
async def embed_batch(config: SentenceTransformersConfig,
                      batch: list[EmbedRow]) -> None
```

Generate embeddings for a batch of content using SentenceTransformers.

Creates vector embeddings for multiple items using SentenceTransformers and
updates the vector field in each EmbedRow object with the resulting embedding.

**Arguments**:

- `config` - Configuration for the SentenceTransformers embedding service.
- `batch` - List of EmbedRow objects containing content to be embedded.
  

**Raises**:

- `AssertionError` - If the number of embeddings returned doesn't match the batch size.

<a id="pgai.semantic_catalog.vectorizer.sentence_tranformers.embed_query"></a>

#### embed\_query

```python
async def embed_query(config: SentenceTransformersConfig,
                      query: str) -> Sequence[float]
```

Generate an embedding for a single query using SentenceTransformers.

Creates a vector embedding for a query string using SentenceTransformers.

**Arguments**:

- `config` - Configuration for the SentenceTransformers embedding service.
- `query` - The query string to embed.
  

**Returns**:

  A vector embedding (sequence of floats) for the query.
  

**Raises**:

- `AssertionError` - If the number of embeddings returned is not exactly 1.

<a id="pgai.semantic_catalog.vectorizer"></a>

# pgai.semantic\_catalog.vectorizer

Vectorizer package for creating and managing vector embeddings in the semantic catalog.

This package provides functionality for converting textual content in the semantic
catalog into vector embeddings using various embedding models. It supports multiple
embedding providers including SentenceTransformers, Ollama, and OpenAI.

The vectorizer package is used to generate embeddings for database objects,
SQL examples, and facts in the semantic catalog, enabling vector similarity search.

<a id="pgai.semantic_catalog.vectorizer.vectorizer"></a>

# pgai.semantic\_catalog.vectorizer.vectorizer

Core vectorizer functionality for the semantic catalog.

This module provides the core functionality for vectorizing content in the semantic catalog.
It includes configuration models for different embedding providers, functions for retrieving
content to be vectorized, and functions for processing and saving embeddings.

The vectorizer supports multiple embedding providers (SentenceTransformers, Ollama, OpenAI)
and can vectorize different types of content (database objects, SQL examples, facts).

<a id="pgai.semantic_catalog.vectorizer.vectorizer.SentenceTransformersConfig"></a>

## SentenceTransformersConfig Objects

```python
class SentenceTransformersConfig(BaseModel)
```

Configuration for SentenceTransformers embedding model.

This class defines the configuration parameters for using SentenceTransformers
as an embedding provider in the semantic catalog.

**Attributes**:

- `implementation` - The implementation type, always "sentence_transformers".
- `config_type` - The configuration type, always "embedding".
- `model` - The name of the SentenceTransformers model to use.
- `dimensions` - The number of dimensions in the resulting embeddings.

<a id="pgai.semantic_catalog.vectorizer.vectorizer.SentenceTransformersConfig.create"></a>

#### create

```python
@classmethod
def create(cls, model: str, dimensions: int)
```

Create a new SentenceTransformersConfig instance.

**Arguments**:

- `model` - The name of the SentenceTransformers model to use.
- `dimensions` - The number of dimensions in the resulting embeddings.
  

**Returns**:

  A new SentenceTransformersConfig instance.

<a id="pgai.semantic_catalog.vectorizer.vectorizer.OllamaConfig"></a>

## OllamaConfig Objects

```python
class OllamaConfig(BaseModel)
```

Configuration for Ollama embedding model.

This class defines the configuration parameters for using Ollama
as an embedding provider in the semantic catalog.

**Attributes**:

- `implementation` - The implementation type, always "ollama".
- `config_type` - The configuration type, always "embedding".
- `model` - The name of the Ollama model to use.
- `dimensions` - The number of dimensions in the resulting embeddings.
- `base_url` - Optional base URL for the Ollama API server.

<a id="pgai.semantic_catalog.vectorizer.vectorizer.OllamaConfig.create"></a>

#### create

```python
@classmethod
def create(cls, model: str, dimensions: int, base_url: str | None = None)
```

Create a new OllamaConfig instance.

**Arguments**:

- `model` - The name of the Ollama model to use.
- `dimensions` - The number of dimensions in the resulting embeddings.
- `base_url` - Optional base URL for the Ollama API server.
  

**Returns**:

  A new OllamaConfig instance.

<a id="pgai.semantic_catalog.vectorizer.vectorizer.OpenAIConfig"></a>

## OpenAIConfig Objects

```python
class OpenAIConfig(BaseModel)
```

Configuration for OpenAI embedding model.

This class defines the configuration parameters for using OpenAI
as an embedding provider in the semantic catalog.

**Attributes**:

- `implementation` - The implementation type, always "openai".
- `config_type` - The configuration type, always "embedding".
- `model` - The name of the OpenAI model to use.
- `dimensions` - The number of dimensions in the resulting embeddings.
- `base_url` - Optional base URL for the OpenAI API server.
- `api_key_name` - Optional name of the environment variable containing the API key.

<a id="pgai.semantic_catalog.vectorizer.vectorizer.OpenAIConfig.create"></a>

#### create

```python
@classmethod
def create(cls,
           model: str,
           dimensions: int,
           base_url: str | None = None,
           api_key_name: str | None = None)
```

Create a new OpenAIConfig instance.

**Arguments**:

- `model` - The name of the OpenAI model to use.
- `dimensions` - The number of dimensions in the resulting embeddings.
- `base_url` - Optional base URL for the OpenAI API server.
- `api_key_name` - Optional name of the environment variable containing the API key.
  

**Returns**:

  A new OpenAIConfig instance.

<a id="pgai.semantic_catalog.vectorizer.vectorizer.embedding_config_from_dict"></a>

#### embedding\_config\_from\_dict

```python
def embedding_config_from_dict(config: dict[str, Any]) -> EmbeddingConfig
```

Create an embedding configuration from a dictionary.

Converts a dictionary representation of an embedding configuration into
the appropriate EmbeddingConfig object based on the implementation.

**Arguments**:

- `config` - Dictionary containing configuration parameters.
  

**Returns**:

  An instance of the appropriate EmbeddingConfig subclass.
  

**Raises**:

- `AssertionError` - If the config is missing an implementation specification.
- `ValueError` - If the implementation is unrecognized.

<a id="pgai.semantic_catalog.vectorizer.vectorizer.vectorize"></a>

#### vectorize

```python
async def vectorize(con: psycopg.AsyncConnection,
                    catalog_id: int,
                    embedding_name: str,
                    config: EmbeddingConfig,
                    batch_size: int = 32) -> None
```

Vectorize content in the semantic catalog.

Processes all database objects, SQL examples, and facts in the semantic catalog
that don't yet have embeddings for the specified embedding name. Generates
embeddings for each item and saves them to the database.

**Arguments**:

- `con` - Asynchronous database connection.
- `catalog_id` - ID of the semantic catalog.
- `embedding_name` - Name of the embedding column to populate.
- `config` - Configuration for the embedding provider to use.
- `batch_size` - Number of items to process in each batch (default: 32).

<a id="pgai.semantic_catalog.vectorizer.vectorizer.vectorize_query"></a>

#### vectorize\_query

```python
async def vectorize_query(config: EmbeddingConfig,
                          query: str) -> Sequence[float]
```

Generate an embedding for a query string.

Creates a vector embedding for a query string using the specified embedding provider.
This is used for semantic search in the catalog.

**Arguments**:

- `config` - Configuration for the embedding provider to use.
- `query` - The query string to embed.
  

**Returns**:

  A vector embedding (sequence of floats) for the query.
  

**Raises**:

- `ValueError` - If the embedding provider configuration is unrecognized.

<a id="pgai.semantic_catalog.vectorizer.openai"></a>

# pgai.semantic\_catalog.vectorizer.openai

OpenAI embedding provider for the semantic catalog vectorizer.

This module implements embedding functionality using OpenAI as the embedding provider.
It provides functions for embedding both batches of content and individual queries.

<a id="pgai.semantic_catalog.vectorizer.openai.embed_batch"></a>

#### embed\_batch

```python
async def embed_batch(config: OpenAIConfig, batch: list[EmbedRow]) -> None
```

Generate embeddings for a batch of content using OpenAI.

Creates vector embeddings for multiple items using the OpenAI API and
updates the vector field in each EmbedRow object with the resulting embedding.

**Arguments**:

- `config` - Configuration for the OpenAI embedding service.
- `batch` - List of EmbedRow objects containing content to be embedded.
  

**Raises**:

- `RuntimeError` - If the number of embeddings returned doesn't match the batch size.

<a id="pgai.semantic_catalog.vectorizer.openai.embed_query"></a>

#### embed\_query

```python
async def embed_query(config: OpenAIConfig, query: str) -> Sequence[float]
```

Generate an embedding for a single query using OpenAI.

Creates a vector embedding for a query string using the OpenAI API.

**Arguments**:

- `config` - Configuration for the OpenAI embedding service.
- `query` - The query string to embed.
  

**Returns**:

  A vector embedding (sequence of floats) for the query.
  

**Raises**:

- `RuntimeError` - If the number of embeddings returned is not exactly 1.

<a id="pgai.semantic_catalog.vectorizer.ollama"></a>

# pgai.semantic\_catalog.vectorizer.ollama

Ollama embedding provider for the semantic catalog vectorizer.

This module implements embedding functionality using Ollama as the embedding provider.
It provides functions for embedding both batches of content and individual queries.

<a id="pgai.semantic_catalog.vectorizer.ollama.embed_batch"></a>

#### embed\_batch

```python
async def embed_batch(config: OllamaConfig, batch: list[EmbedRow]) -> None
```

Generate embeddings for a batch of content using Ollama.

Creates vector embeddings for multiple items using the Ollama API and
updates the vector field in each EmbedRow object with the resulting embedding.

**Arguments**:

- `config` - Configuration for the Ollama embedding service.
- `batch` - List of EmbedRow objects containing content to be embedded.
  

**Raises**:

- `RuntimeError` - If the number of embeddings returned doesn't match the batch size.

<a id="pgai.semantic_catalog.vectorizer.ollama.embed_query"></a>

#### embed\_query

```python
async def embed_query(config: OllamaConfig, query: str) -> Sequence[float]
```

Generate an embedding for a single query using Ollama.

Creates a vector embedding for a query string using the Ollama API.

**Arguments**:

- `config` - Configuration for the Ollama embedding service.
- `query` - The query string to embed.
  

**Returns**:

  A vector embedding (sequence of floats) for the query.
  

**Raises**:

- `RuntimeError` - If the number of embeddings returned is not exactly 1.

<a id="pgai.semantic_catalog.render"></a>

# pgai.semantic\_catalog.render

<a id="pgai.semantic_catalog.render.render_table"></a>

#### render\_table

```python
def render_table(table: Table) -> str
```

Render a table object using the table template.

**Arguments**:

- `table` - The Table object to render.
  

**Returns**:

  The rendered table as a string.

<a id="pgai.semantic_catalog.render.render_tables"></a>

#### render\_tables

```python
def render_tables(tables: Iterable[Table]) -> str
```

Render multiple table objects.

**Arguments**:

- `tables` - An iterable of Table objects to render.
  

**Returns**:

  A string containing all rendered tables separated by newlines.

<a id="pgai.semantic_catalog.render.render_view"></a>

#### render\_view

```python
def render_view(view: View) -> str
```

Render a view object using the view template.

**Arguments**:

- `view` - The View object to render.
  

**Returns**:

  The rendered view as a string.

<a id="pgai.semantic_catalog.render.render_views"></a>

#### render\_views

```python
def render_views(views: Iterable[View]) -> str
```

Render multiple view objects.

**Arguments**:

- `views` - An iterable of View objects to render.
  

**Returns**:

  A string containing all rendered views separated by newlines.

<a id="pgai.semantic_catalog.render.render_procedure"></a>

#### render\_procedure

```python
def render_procedure(proc: Procedure) -> str
```

Render a procedure object using the procedure template.

**Arguments**:

- `proc` - The Procedure object to render.
  

**Returns**:

  The rendered procedure as a string.

<a id="pgai.semantic_catalog.render.render_procedures"></a>

#### render\_procedures

```python
def render_procedures(procedures: Iterable[Procedure]) -> str
```

Render multiple procedure objects.

**Arguments**:

- `procedures` - An iterable of Procedure objects to render.
  

**Returns**:

  A string containing all rendered procedures separated by newlines.

<a id="pgai.semantic_catalog.render.render_object"></a>

#### render\_object

```python
def render_object(object: Table | View | Procedure) -> str
```

Render a database object based on its type.

**Arguments**:

- `object` - A database object (Table, View, or Procedure) to render.
  

**Returns**:

  The rendered object as a string.

<a id="pgai.semantic_catalog.render.render_objects"></a>

#### render\_objects

```python
def render_objects(objects: Iterable[Table | View | Procedure]) -> str
```

Render multiple database objects of various types.

**Arguments**:

- `objects` - An iterable of database objects (Tables, Views, or Procedures) to render.
  

**Returns**:

  A string containing all rendered objects separated by newlines.

<a id="pgai.semantic_catalog.render.render_fact"></a>

#### render\_fact

```python
def render_fact(fact: Fact) -> str
```

Render a fact object using the fact template.

**Arguments**:

- `fact` - The Fact object to render.
  

**Returns**:

  The rendered fact as a string.

<a id="pgai.semantic_catalog.render.render_facts"></a>

#### render\_facts

```python
def render_facts(facts: Iterable[Fact]) -> str
```

Render multiple fact objects.

**Arguments**:

- `facts` - An iterable of Fact objects to render.
  

**Returns**:

  A string containing all rendered facts separated by newlines.

<a id="pgai.semantic_catalog.render.render_sql_example"></a>

#### render\_sql\_example

```python
def render_sql_example(example: SQLExample) -> str
```

Render a SQL example object using the sql_example template.

**Arguments**:

- `example` - The SQLExample object to render.
  

**Returns**:

  The rendered SQL example as a string.

<a id="pgai.semantic_catalog.render.render_sql_examples"></a>

#### render\_sql\_examples

```python
def render_sql_examples(examples: Iterable[SQLExample]) -> str
```

Render multiple SQL example objects.

**Arguments**:

- `examples` - An iterable of SQLExample objects to render.
  

**Returns**:

  A string containing all rendered SQL examples separated by newlines.

<a id="pgai.semantic_catalog.file"></a>

# pgai.semantic\_catalog.file

<a id="pgai.semantic_catalog.file.item_from_dict"></a>

#### item\_from\_dict

```python
def item_from_dict(d: dict[str, Any]) -> Item
```

Convert a dictionary to the appropriate catalog item type.

Takes a dictionary that represents a catalog item and converts it to the
corresponding model class based on the 'type' field.

**Arguments**:

- `d` - Dictionary containing item data with a 'type' field.
  

**Returns**:

  An instance of the appropriate Item type.
  

**Raises**:

- `ValueError` - If the 'type' field is not recognized.

<a id="pgai.semantic_catalog.file.import_from_yaml"></a>

#### import\_from\_yaml

```python
def import_from_yaml(text: TextIO) -> Generator[Item, None, None]
```

Import catalog items from a YAML file.

Reads a YAML stream containing multiple documents. The first document should be a
header with schema version information, followed by one or more catalog items.

**Arguments**:

- `text` - A text IO stream containing YAML documents.
  

**Returns**:

  A generator yielding catalog items (Tables, Views, Functions, etc.).
  

**Raises**:

- `RuntimeError` - If the first document is not a header or has an invalid schema version.

<a id="pgai.semantic_catalog.file.save_to_catalog"></a>

#### save\_to\_catalog

```python
async def save_to_catalog(catalog_con: psycopg.AsyncConnection,
                          target_con: psycopg.AsyncConnection, catalog_id: int,
                          items: Iterator[Item]) -> None
```

Save catalog items to the semantic catalog database.

Takes a collection of catalog items and saves them to the semantic catalog database.
Resolves object IDs from the target database and creates appropriate descriptions.

**Arguments**:

- `catalog_con` - Asynchronous database connection to the catalog database.
- `target_con` - Asynchronous database connection to the target database (where objects are defined).
- `catalog_id` - ID of the semantic catalog to save to.
- `items` - Iterator of catalog items to save.

<a id="pgai.semantic_catalog.file.load_from_catalog"></a>

#### load\_from\_catalog

```python
async def load_from_catalog(con: psycopg.AsyncConnection,
                            catalog_id: int) -> AsyncGenerator[Item, None]
```

Load all items from the semantic catalog.

Retrieves all catalog items (tables, views, functions, procedures, aggregates,
SQL examples, and facts) from the specified semantic catalog.

**Arguments**:

- `con` - Asynchronous database connection to the catalog database.
- `catalog_id` - ID of the semantic catalog to load from.
  

**Returns**:

  An async generator yielding all catalog items.

<a id="pgai.semantic_catalog.file.export_to_yaml"></a>

#### export\_to\_yaml

```python
def export_to_yaml(text: TextIO, items: Iterator[Item]) -> None
```

Export catalog items to a YAML file.

Writes catalog items to a YAML file with multiple documents. The first document
is a header with schema version information, followed by one document per item.

**Arguments**:

- `text` - A text IO stream to write the YAML documents to.
- `items` - Iterator of catalog items to export.

<a id="pgai.semantic_catalog.file.async_export_to_yaml"></a>

#### async\_export\_to\_yaml

```python
async def async_export_to_yaml(text: TextIO,
                               items: AsyncIterator[Item]) -> None
```

Export catalog items to a YAML file asynchronously.

Asynchronously writes catalog items to a YAML file with multiple documents. The first document
is a header with schema version information, followed by one document per item.

**Arguments**:

- `text` - A text IO stream to write the YAML documents to.
- `items` - Async iterator of catalog items to export.

<a id="pgai.semantic_catalog.loader"></a>

# pgai.semantic\_catalog.loader

<a id="pgai.semantic_catalog.loader.load_tables"></a>

#### load\_tables

```python
async def load_tables(con: psycopg.AsyncConnection,
                      oids: list[int],
                      sample_size: int = 0) -> list[Table]
```

Load table definitions from the database based on object IDs.

Retrieves table metadata including columns, constraints, and indexes for the
specified table OIDs. If sample_size is greater than 0, it also retrieves sample
data from each table.

**Arguments**:

- `con` - Asynchronous database connection object.
- `oids` - List of table object IDs to load.
- `sample_size` - Number of sample rows to retrieve from each table (default: 0).
  If 0, no sample data is retrieved.
  

**Returns**:

  A list of Table objects with metadata and optionally sample data.
  

**Raises**:

- `AssertionError` - If the list of oids is empty.

<a id="pgai.semantic_catalog.loader.load_views"></a>

#### load\_views

```python
async def load_views(con: psycopg.AsyncConnection,
                     oids: list[int],
                     sample_size: int = 0) -> list[View]
```

Load view definitions from the database based on object IDs.

Retrieves view metadata including columns and definition SQL for the specified
view OIDs. Handles both regular views and materialized views. If TimescaleDB is
installed, it also identifies continuous aggregates. If sample_size is greater
than 0, it also retrieves sample data from each view.

**Arguments**:

- `con` - Asynchronous database connection object.
- `oids` - List of view object IDs to load.
- `sample_size` - Number of sample rows to retrieve from each view (default: 0).
  If 0, no sample data is retrieved.
  

**Returns**:

  A list of View objects with metadata and optionally sample data.
  

**Raises**:

- `AssertionError` - If the list of oids is empty.

<a id="pgai.semantic_catalog.loader.load_procedures"></a>

#### load\_procedures

```python
async def load_procedures(con: psycopg.AsyncConnection,
                          oids: list[int]) -> list[Procedure]
```

Load procedure definitions from the database based on object IDs.

Retrieves metadata for procedures, functions, and aggregates for the specified OIDs,
including their full definition SQL.

**Arguments**:

- `con` - Asynchronous database connection object.
- `oids` - List of procedure object IDs to load.
  

**Returns**:

  A list of Procedure objects with metadata.
  

**Raises**:

- `AssertionError` - If the list of oids is empty.

<a id="pgai.semantic_catalog.loader.load_objects"></a>

#### load\_objects

```python
async def load_objects(catalog_con: psycopg.AsyncConnection,
                       target_con: psycopg.AsyncConnection,
                       catalog_id: int,
                       obj_desc: list[ObjectDescription],
                       sample_size: int = 0) -> list[Table | View | Procedure]
```

Load database objects based on their descriptions.

Takes a list of object descriptions and loads the corresponding database objects
(tables, views, procedures) with their metadata. Matches the descriptions with
the loaded objects and attaches them. If sample_size is greater than 0, it also
retrieves sample data for tables and views.

**Arguments**:

- `catalog_con` - Connection to the semantic catalog database.
- `target_con` - Connection to the target database where the objects are defined.
- `catalog_id` - ID of the semantic catalog to use for retrieving descriptions.
- `obj_desc` - List of object descriptions to match with database objects.
- `sample_size` - Number of sample rows to retrieve from tables and views (default: 0).
  If 0, no sample data is retrieved.
  

**Returns**:

  A list of database objects (Tables, Views, Procedures) with metadata and descriptions.
  

**Raises**:

- `ValueError` - If an unknown object type is encountered.

<a id="pgai.semantic_catalog.fix"></a>

# pgai.semantic\_catalog.fix

Database object reference fixing utilities for semantic catalog.

This module provides functions to fix database object references in the semantic
catalog. When database objects like tables, views, or columns are changed, their
internal identifiers and object names might need to be updated in the semantic catalog
to maintain proper references.

<a id="pgai.semantic_catalog.fix._Object"></a>

## \_Object Objects

```python
@dataclass
class _Object()
```

Represents a database object reference stored in the semantic catalog.

Contains both PostgreSQL internal identifiers (classid, objid, objsubid) and
object name identifiers (objtype, objnames, objargs) for a database object.

<a id="pgai.semantic_catalog.fix._Object.id"></a>

#### id

Semantic catalog object ID

<a id="pgai.semantic_catalog.fix._Object.classid"></a>

#### classid

PostgreSQL pg_class.oid for the system catalog containing the object

<a id="pgai.semantic_catalog.fix._Object.objid"></a>

#### objid

PostgreSQL oid of the object in the system catalog

<a id="pgai.semantic_catalog.fix._Object.objsubid"></a>

#### objsubid

Sub-object ID for columns and other sub-objects

<a id="pgai.semantic_catalog.fix._Object.objtype"></a>

#### objtype

Type of object (table, view, function, etc.)

<a id="pgai.semantic_catalog.fix._Object.objnames"></a>

#### objnames

Fully qualified object name as a list of identifiers

<a id="pgai.semantic_catalog.fix._Object.objargs"></a>

#### objargs

Function arguments (if applicable)

<a id="pgai.semantic_catalog.fix._Ids"></a>

## \_Ids Objects

```python
@dataclass
class _Ids()
```

Container for PostgreSQL internal object identifiers.

Represents the system identifiers for a PostgreSQL database object,
as returned by pg_get_object_address().

<a id="pgai.semantic_catalog.fix._Ids.classid"></a>

#### classid

PostgreSQL pg_class.oid for the system catalog containing the object

<a id="pgai.semantic_catalog.fix._Ids.objid"></a>

#### objid

PostgreSQL oid of the object in the system catalog

<a id="pgai.semantic_catalog.fix._Ids.objsubid"></a>

#### objsubid

Sub-object ID for columns and other sub-objects

<a id="pgai.semantic_catalog.fix._Names"></a>

## \_Names Objects

```python
@dataclass
class _Names()
```

Container for PostgreSQL object name identifiers.

Represents the name-based identifiers for a PostgreSQL database object,
as returned by pg_identify_object_as_address().

<a id="pgai.semantic_catalog.fix._Names.objtype"></a>

#### objtype

Type of object (table, view, function, etc.)

<a id="pgai.semantic_catalog.fix._Names.objnames"></a>

#### objnames

Fully qualified object name as a list of identifiers

<a id="pgai.semantic_catalog.fix._Names.objargs"></a>

#### objargs

Function arguments (if applicable)

<a id="pgai.semantic_catalog.fix.fix_ids"></a>

#### fix\_ids

```python
async def fix_ids(catalog_con: psycopg.AsyncConnection,
                  target_con: psycopg.AsyncConnection, catalog_id: int,
                  dry_run: bool, console: Console) -> None
```

Fix internal PostgreSQL IDs in the semantic catalog.

Checks all objects in the semantic catalog against the target database. For each object:
- If object doesn't exist in target database, marks it for deletion
- If object's internal IDs don't match current values, marks it for update
- If object is already correct, leaves it unchanged

If not a dry run, performs all deletions and updates in a transaction.
Shows progress with a rich progress bar.

**Arguments**:

- `catalog_con` - Connection to the database containing the semantic catalog
- `target_con` - Connection to the target database containing the actual objects
- `catalog_id` - ID of the semantic catalog to fix
- `dry_run` - If True, only check for issues without making changes
- `console` - Rich console for output and progress display

<a id="pgai.semantic_catalog.fix.fix_names"></a>

#### fix\_names

```python
async def fix_names(catalog_con: psycopg.AsyncConnection,
                    target_con: psycopg.AsyncConnection, catalog_id: int,
                    dry_run: bool, console: Console) -> None
```

Fix object name identifiers in the semantic catalog.

Checks all objects in the semantic catalog against the target database. For each object:
- If object doesn't exist in target database, marks it for deletion
- If object's name identifiers don't match current values, marks it for update
- If object is already correct, leaves it unchanged

If not a dry run, performs all deletions and updates in a transaction.
Shows progress with a rich progress bar.

**Arguments**:

- `catalog_con` - Connection to the database containing the semantic catalog
- `target_con` - Connection to the target database containing the actual objects
- `catalog_id` - ID of the semantic catalog to fix
- `dry_run` - If True, only check for issues without making changes
- `console` - Rich console for output and progress display

<a id="pgai.semantic_catalog.gen_sql"></a>

# pgai.semantic\_catalog.gen\_sql

Module for generating SQL statements using AI and semantic catalog context.

This module provides functionality to generate valid SQL statements based on natural
language prompts and database context from the semantic catalog. It uses semantic search
to find relevant database objects, SQL examples, and facts, and employs an AI model to
generate SQL that fulfills the user's request. The generated SQL is validated against
the target database to ensure correctness.

<a id="pgai.semantic_catalog.gen_sql.DatabaseContext"></a>

## DatabaseContext Objects

```python
@dataclass
class DatabaseContext()
```

Container for database objects, SQL examples, facts, and their rendered representations.

This class stores references to database objects (tables, views, procedures),
SQL examples, and facts that are relevant to a user query, along with their
rendered text representations for use in prompt construction.

**Attributes**:

- `objects` - Dictionary mapping object IDs to database objects (Tables, Views, Procedures).
- `sql_examples` - Dictionary mapping SQL example IDs to SQLExample objects.
- `facts` - Dictionary mapping fact IDs to Fact objects.
- `rendered_objects` - Dictionary mapping object IDs to their rendered text representations.
- `rendered_sql_examples` - Dictionary mapping SQL example IDs to their rendered text representations.
- `rendered_facts` - Dictionary mapping fact IDs to their rendered text representations.

<a id="pgai.semantic_catalog.gen_sql.fetch_database_context"></a>

#### fetch\_database\_context

```python
async def fetch_database_context(catalog_con: psycopg.AsyncConnection,
                                 target_con: psycopg.AsyncConnection,
                                 catalog_id: int,
                                 embedding_name: str,
                                 embedding_config: EmbeddingConfig,
                                 prompt: str,
                                 ctx: DatabaseContext | None = None,
                                 sample_size: int = 3) -> DatabaseContext
```

Fetch database context relevant to a prompt using semantic search.

Performs semantic search in the catalog to find database objects, SQL examples,
and facts that are relevant to the given prompt. The retrieved items are added to
the provided context (or a new context is created if none is provided).

**Arguments**:

- `catalog_con` - Connection to the semantic catalog database.
- `target_con` - Connection to the target database (where the objects are defined).
- `catalog_id` - ID of the semantic catalog to search in.
- `embedding_name` - Name of the embedding column to use for semantic search.
- `embedding_config` - Configuration for the embedding model.
- `prompt` - The natural language prompt to search for relevant context.
- `ctx` - Optional existing DatabaseContext to add to (None creates a new one).
- `sample_size` - Number of sample rows to include for tables and views (default: 3).
  

**Returns**:

  A DatabaseContext containing the relevant database objects, SQL examples, and facts.

<a id="pgai.semantic_catalog.gen_sql.fetch_database_context_alt"></a>

#### fetch\_database\_context\_alt

```python
async def fetch_database_context_alt(catalog_con: psycopg.AsyncConnection,
                                     target_con: psycopg.AsyncConnection,
                                     catalog_id: int,
                                     obj_ids: list[int] | None = None,
                                     sql_ids: list[int] | None = None,
                                     fact_ids: list[int] | None = None,
                                     sample_size: int = 3) -> DatabaseContext
```

Fetch database context by explicit IDs or fetch all items from the catalog.

Retrieves database objects, SQL examples, and facts from the semantic catalog based
on either explicit IDs or by fetching all items if no IDs are provided.

**Arguments**:

- `catalog_con` - Connection to the semantic catalog database.
- `target_con` - Connection to the target database (where the objects are defined).
- `catalog_id` - ID of the semantic catalog to fetch from.
- `obj_ids` - Optional list of object IDs to fetch (None fetches all).
- `sql_ids` - Optional list of SQL example IDs to fetch (None fetches all).
- `fact_ids` - Optional list of fact IDs to fetch (None fetches all).
- `sample_size` - Number of sample rows to include for tables and views (default: 3).
  

**Returns**:

  A DatabaseContext containing the specified database objects, SQL examples, and facts.

<a id="pgai.semantic_catalog.gen_sql.validate_sql_statement"></a>

#### validate\_sql\_statement

```python
async def validate_sql_statement(
        target_con: psycopg.AsyncConnection,
        sql_statement: str) -> tuple[dict[str, Any] | None, str | None]
```

Validate a SQL statement against the database.

Attempts to execute an EXPLAIN command for the SQL statement to verify that it is
syntactically correct and can be executed on the target database. This is done in
a transaction that is rolled back to prevent any modifications to the database.

**Arguments**:

- `target_con` - Connection to the target database.
- `sql_statement` - The SQL statement to validate.
  

**Returns**:

  A tuple containing:
  - The query plan as a dictionary if validation succeeds, None otherwise.
  - The error message if validation fails, None otherwise.

<a id="pgai.semantic_catalog.gen_sql.GenerateSQLResponse"></a>

## GenerateSQLResponse Objects

```python
@dataclass
class GenerateSQLResponse()
```

Response object for the generate_sql function.

Contains the generated SQL statement, the context used to generate it,
the query plan, and additional information about the generation process.

**Attributes**:

- `sql_statement` - The generated SQL statement.
- `context` - The database context used to generate the SQL statement.
- `command_type` - The type of SQL statement generated (e.g. SELECT, INSERT, UPDATE)
- `query_plan` - The PostgreSQL query plan for the generated SQL statement.
- `final_prompt` - The final prompt that was sent to the model.
- `messages` - List of all messages exchanged during the generation process.
- `usage` - Usage statistics for the AI model calls.

<a id="pgai.semantic_catalog.gen_sql.initialize_database_context"></a>

#### initialize\_database\_context

```python
async def initialize_database_context(
        catalog_con: psycopg.AsyncConnection,
        target_con: psycopg.AsyncConnection,
        catalog_id: int,
        embedding_name: str,
        embedding_config: EmbeddingConfig,
        prompt: str,
        sample_size: int = 3,
        context_mode: ContextMode = "semantic_search",
        obj_ids: list[int] | None = None,
        sql_ids: list[int] | None = None,
        fact_ids: list[int] | None = None) -> DatabaseContext
```

Initialize database context based on the specified context mode.

This function serves as a dispatcher to initialize the database context using
one of three strategies:
1. Semantic search: Find relevant items based on the prompt.
2. Entire catalog: Fetch all items from the catalog.
3. Specific IDs: Fetch items with the specified IDs.

**Arguments**:

- `catalog_con` - Connection to the semantic catalog database.
- `target_con` - Connection to the target database.
- `catalog_id` - ID of the semantic catalog.
- `embedding_name` - Name of the embedding column to use for semantic search.
- `embedding_config` - Configuration for the embedding model.
- `prompt` - The natural language prompt to search for relevant context.
- `sample_size` - Number of sample rows to include for tables and views (default: 3).
- `context_mode` - The mode to use for initializing the context (default: "semantic_search").
- `obj_ids` - Optional list of object IDs to fetch (for "specific_ids" mode).
- `sql_ids` - Optional list of SQL example IDs to fetch (for "specific_ids" mode).
- `fact_ids` - Optional list of fact IDs to fetch (for "specific_ids" mode).
  

**Returns**:

  A DatabaseContext based on the specified context mode.
  

**Raises**:

- `AssertionError` - If the context_mode is not one of the supported values.

<a id="pgai.semantic_catalog.gen_sql.IterationLimitExceededException"></a>

## IterationLimitExceededException Objects

```python
class IterationLimitExceededException(Exception)
```

Exception raised when iteration limit exceeded.

<a id="pgai.semantic_catalog.gen_sql.generate_sql"></a>

#### generate\_sql

```python
async def generate_sql(
        catalog_con: psycopg.AsyncConnection,
        target_con: psycopg.AsyncConnection,
        model: KnownModelName | Model,
        catalog_id: int,
        embedding_name: str,
        embedding_config: EmbeddingConfig,
        prompt: str,
        usage: Usage | None = None,
        usage_limits: UsageLimits | None = None,
        model_settings: ModelSettings | None = None,
        iteration_limit: int = 10,
        sample_size: int = 3,
        context_mode: ContextMode = "semantic_search",
        obj_ids: list[int] | None = None,
        sql_ids: list[int] | None = None,
        fact_ids: list[int] | None = None) -> GenerateSQLResponse
```

Generate a SQL statement based on natural language prompt and database context.
This function uses an AI model to generate a SQL statement that fulfills the user's
request, drawing on context from the semantic catalog about database objects, SQL
examples, and facts. The generated SQL is validated against the target database
to ensure correctness, and refinement iterations are performed if needed.
The function uses an iterative approach:
1. Initialize database context based on the specified context mode
2. Generate a SQL statement using the AI model with the context
3. Validate the SQL statement against the target database
4. If invalid, refine the SQL statement with error feedback
5. Repeat until a valid SQL statement is generated or iteration limit is reached

**Arguments**:

- `catalog_con` - Connection to the semantic catalog database.
- `target_con` - Connection to the target database where SQL will be executed.
- `model` - AI model to use for generating SQL (KnownModelName or Model instance).
- `catalog_id` - ID of the semantic catalog to use for context.
- `embedding_name` - Name of the embedding column to use for semantic search.
- `embedding_config` - Configuration for the embedding model.
- `prompt` - Natural language prompt describing the desired SQL statement.
- `usage` - Optional Usage object to track token usage across calls.
- `usage_limits` - Optional limits on token usage and requests.
- `model_settings` - Optional settings for the AI model.
- `iteration_limit` - Maximum number of refinement iterations (default: 5).
- `sample_size` - Number of sample rows to include for tables/views (default: 3).
- `context_mode` - Strategy for initializing database context:
  - "semantic_search": Find relevant items semantically (default)
  - "entire_catalog": Include all items from the catalog
  - "specific_ids": Include only items with specified IDs
- `obj_ids` - Optional list of database object IDs to include (for "specific_ids" mode).
- `sql_ids` - Optional list of SQL example IDs to include (for "specific_ids" mode).
- `fact_ids` - Optional list of fact IDs to include (for "specific_ids" mode).

**Returns**:

  A GenerateSQLResponse containing:
  - The generated SQL statement
  - The database context used for generation
  - The query plan for the SQL statement
  - The final prompt sent to the model
  - The final response from the model
  - All messages exchanged during generation
  - Usage statistics for the AI model calls

**Raises**:

- `IterationLimitExceededException` - If the iteration limit is reached without
  generating a valid SQL statement.
- `RuntimeError` - If the semantic catalog is not properly configured.

**Example**:

    ```python
    # Generate a SQL statement for a natural language query
    response = await generate_sql(
        catalog_con=catalog_connection,
        target_con=db_connection,
        model="anthropic:claude-3-opus-20240229",
        catalog_id=1,
        embedding_name="openai_embeddings",
        embedding_config=config,
        prompt="Find all orders placed last month with a total value over $1000",
        iteration_limit=3,
    )
    # Use the generated SQL
    print(response.sql_statement)
    ```

<a id="pgai.semantic_catalog.sample"></a>

# pgai.semantic\_catalog.sample

<a id="pgai.semantic_catalog.sample.sample_table"></a>

#### sample\_table

```python
async def sample_table(con: psycopg.AsyncConnection,
                       schema_name: str,
                       table_name: str,
                       limit: int = 3,
                       format: str = "copy_text") -> str
```

Sample data from a database table.

Retrieves a limited number of rows from the specified table and formats the data
according to the specified format.

**Arguments**:

- `con` - Asynchronous database connection object.
- `schema_name` - Name of the schema containing the table.
- `table_name` - Name of the table to sample.
- `limit` - Maximum number of rows to sample (default: 3).
- `format` - Output format, either "inserts" or "copy_text" (default: "copy_text").
  

**Returns**:

  A string containing the sampled data in the requested format.
  

**Raises**:

- `RuntimeError` - If an unsupported format is specified.

<a id="pgai.semantic_catalog.sample.sample_view"></a>

#### sample\_view

```python
async def sample_view(con: psycopg.AsyncConnection,
                      schema_name: str,
                      view_name: str,
                      limit: int = 3,
                      format: str = "copy_text") -> str
```

Sample data from a database view.

Retrieves a limited number of rows from the specified view and formats the data
according to the specified format.

**Arguments**:

- `con` - Asynchronous database connection object.
- `schema_name` - Name of the schema containing the view.
- `view_name` - Name of the view to sample.
- `limit` - Maximum number of rows to sample (default: 3).
- `format` - Output format, either "inserts" or "copy_text" (default: "copy_text").
  

**Returns**:

  A string containing the sampled data in the requested format.
  

**Raises**:

- `RuntimeError` - If an unsupported format is specified.

<a id="pgai.semantic_catalog.search"></a>

# pgai.semantic\_catalog.search

<a id="pgai.semantic_catalog.search.search_objects"></a>

#### search\_objects

```python
async def search_objects(
        con: psycopg.AsyncConnection,
        catalog_id: int,
        embedding_name: str,
        config: EmbeddingConfig,
        query: Sequence[float],
        limit: int = 5,
        exclude_ids: Sequence[int] | None = None) -> list[ObjectDescription]
```

Search for database objects in the semantic catalog using vector similarity.

Performs a semantic search for database objects (tables, views, functions, etc.)
using vector similarity between the query embedding and object embeddings.

**Arguments**:

- `con` - Asynchronous database connection to the catalog database.
- `catalog_id` - ID of the semantic catalog to search in.
- `embedding_name` - Name of the embedding column to search in.
- `config` - Configuration for the embedding model used.
- `query` - Query vector (embedding) to compare against stored object embeddings.
- `limit` - Maximum number of results to return (default: 5).
- `exclude_ids` - ids of objects to exclude from search results
  

**Returns**:

  A list of ObjectDescription objects ordered by similarity to the query vector.

<a id="pgai.semantic_catalog.search.search_sql_examples"></a>

#### search\_sql\_examples

```python
async def search_sql_examples(
        con: psycopg.AsyncConnection,
        catalog_id: int,
        embedding_name: str,
        config: EmbeddingConfig,
        query: Sequence[float],
        limit: int = 5,
        exclude_ids: Sequence[int] | None = None) -> list[SQLExample]
```

Search for SQL examples in the semantic catalog using vector similarity.

Performs a semantic search for SQL examples using vector similarity between
the query embedding and SQL example embeddings.

**Arguments**:

- `con` - Asynchronous database connection to the catalog database.
- `catalog_id` - ID of the semantic catalog to search in.
- `embedding_name` - Name of the embedding column to search in.
- `config` - Configuration for the embedding model used.
- `query` - Query vector (embedding) to compare against stored SQL example embeddings.
- `limit` - Maximum number of results to return (default: 5).
- `exclude_ids` - ids of sql examples to exclude from search results
  

**Returns**:

  A list of SQLExample objects ordered by similarity to the query vector.

<a id="pgai.semantic_catalog.search.search_facts"></a>

#### search\_facts

```python
async def search_facts(con: psycopg.AsyncConnection,
                       catalog_id: int,
                       embedding_name: str,
                       config: EmbeddingConfig,
                       query: Sequence[float],
                       limit: int = 5,
                       exclude_ids: Sequence[int] | None = None) -> list[Fact]
```

Search for facts in the semantic catalog using vector similarity.

Performs a semantic search for facts using vector similarity between
the query embedding and fact embeddings.

**Arguments**:

- `con` - Asynchronous database connection to the catalog database.
- `catalog_id` - ID of the semantic catalog to search in.
- `embedding_name` - Name of the embedding column to search in.
- `config` - Configuration for the embedding model used.
- `query` - Query vector (embedding) to compare against stored fact embeddings.
- `limit` - Maximum number of results to return (default: 5).
- `exclude_ids` - ids of facts to exclude from search results
  

**Returns**:

  A list of Fact objects ordered by similarity to the query vector.

<a id="pgai.semantic_catalog.templates"></a>

# pgai.semantic\_catalog.templates

Templates module for the semantic catalog.

This module provides a Jinja2 environment and templates for rendering database objects
(tables, views, procedures), SQL examples, facts, and prompts for SQL generation.
The templates are used to format the catalog items for display, export, and AI
interaction.

<a id="pgai.semantic_catalog.exceptions"></a>

# pgai.semantic\_catalog.exceptions

<a id="pgai.semantic_catalog.semantic_catalog"></a>

# pgai.semantic\_catalog.semantic\_catalog

Semantic Catalog module for managing database metadata and descriptions.

This module provides the core functionality for creating, managing, and interacting with
semantic catalogs. A semantic catalog stores metadata about database objects (tables,
views, procedures, etc.) along with natural language descriptions and vector embeddings
for semantic search capabilities.

The semantic catalog enables natural language queries about database schema, generating
SQL based on natural language prompts, and managing database documentation.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog"></a>

## SemanticCatalog Objects

```python
class SemanticCatalog()
```

Represents a semantic catalog in the database.

A semantic catalog is a collection of database object metadata, descriptions,
and vector embeddings that enable semantic search capabilities and natural
language interactions with the database schema.

**Attributes**:

- `id` - The unique identifier of the semantic catalog.
- `name` - The name of the semantic catalog.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.__init__"></a>

#### \_\_init\_\_

```python
def __init__(id: int, name: str)
```

Initialize a SemanticCatalog instance.

**Arguments**:

- `id` - The unique identifier of the semantic catalog.
- `name` - The name of the semantic catalog.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.id"></a>

#### id

```python
@property
def id() -> int
```

Get the unique identifier of the semantic catalog.

**Returns**:

  The semantic catalog ID.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.name"></a>

#### name

```python
@property
def name() -> str
```

Get the name of the semantic catalog.

**Returns**:

  The semantic catalog name.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.drop"></a>

#### drop

```python
async def drop(con: CatalogConnection) -> None
```

Drop the semantic catalog from the database.

Deletes the semantic catalog and all its associated data from the database.

**Arguments**:

- `con` - The database connection to the catalog database.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.add_embedding"></a>

#### add\_embedding

```python
async def add_embedding(
        con: CatalogConnection,
        config: EmbeddingConfig,
        embedding_name: str | None = None) -> tuple[str, EmbeddingConfig]
```

Add an embedding configuration to the semantic catalog.

Creates a new embedding configuration in the semantic catalog. If an embedding name
is not provided, a default name will be generated.

**Arguments**:

- `con` - The database connection to the catalog database.
- `config` - The embedding configuration to add.
- `embedding_name` - Optional name for the embedding. If not provided, a default
  name will be generated.
  

**Returns**:

  A tuple containing the embedding name and the embedding configuration that was added.
  

**Raises**:

- `RuntimeError` - If the embedding could not be added.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.drop_embedding"></a>

#### drop\_embedding

```python
async def drop_embedding(con: CatalogConnection, embedding_name: str)
```

Drop an embedding configuration from the semantic catalog.

Removes an embedding configuration and all its associated embeddings from the
semantic catalog.

**Arguments**:

- `con` - The database connection to the catalog database.
- `embedding_name` - Name of the embedding configuration to drop.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.list_embeddings"></a>

#### list\_embeddings

```python
async def list_embeddings(
        con: CatalogConnection) -> list[tuple[str, EmbeddingConfig]]
```

List all embedding configurations in the semantic catalog.

Retrieves all embedding configurations defined in the semantic catalog.

**Arguments**:

- `con` - The database connection to the catalog database.
  

**Returns**:

  A list of tuples, each containing an embedding name and its configuration.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.get_embedding"></a>

#### get\_embedding

```python
async def get_embedding(con: CatalogConnection,
                        embedding_name: str) -> EmbeddingConfig | None
```

Get a specific embedding configuration from the semantic catalog.

Retrieves a single embedding configuration by name.

**Arguments**:

- `con` - The database connection to the catalog database.
- `embedding_name` - Name of the embedding configuration to retrieve.
  

**Returns**:

  The embedding configuration if found, None otherwise.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.vectorize"></a>

#### vectorize

```python
async def vectorize(con: psycopg.AsyncConnection,
                    embedding_name: str,
                    config: EmbeddingConfig,
                    batch_size: int = 32) -> None
```

Generate vector embeddings for items in the semantic catalog.

Processes all database objects, SQL examples, and facts in the semantic catalog
that don't yet have embeddings for the specified embedding configuration.

**Arguments**:

- `con` - The database connection to the catalog database.
- `embedding_name` - Name of the embedding configuration to use.
- `config` - The embedding configuration to use.
- `batch_size` - Number of items to process in each batch.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.vectorize_all"></a>

#### vectorize\_all

```python
async def vectorize_all(con: CatalogConnection, batch_size: int = 32)
```

Generate vector embeddings for all embedding configurations.

Processes all database objects, SQL examples, and facts in the semantic catalog
for all embedding configurations defined in the catalog.

**Arguments**:

- `con` - The database connection to the catalog database.
- `batch_size` - Number of items to process in each batch.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.list_objects"></a>

#### list\_objects

```python
async def list_objects(con: CatalogConnection,
                       objtype: str | None = None) -> list[ObjectDescription]
```

List all database objects in the semantic catalog.

Retrieves all database objects (tables, views, procedures) stored in the
semantic catalog.

**Arguments**:

- `con` - The database connection to the catalog database.
- `objtype` - Optional type of object to filter by (e.g., "table", "view").
  

**Returns**:

  A list of ObjectDescription objects.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.search_objects"></a>

#### search\_objects

```python
async def search_objects(con: CatalogConnection,
                         embedding_name: str,
                         query: str | Sequence[float],
                         limit: int = 5) -> list[ObjectDescription]
```

Search for database objects using semantic search.

Performs a semantic search for database objects that match the query.
The query can be a natural language string or a vector embedding.

**Arguments**:

- `con` - The database connection to the catalog database.
- `embedding_name` - Name of the embedding configuration to use for the search.
- `query` - Natural language query string or vector embedding.
- `limit` - Maximum number of results to return.
  

**Returns**:

  A list of ObjectDescription objects ordered by similarity to the query.
  

**Raises**:

- `RuntimeError` - If the specified embedding configuration does not exist.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.list_sql_examples"></a>

#### list\_sql\_examples

```python
async def list_sql_examples(con: CatalogConnection) -> list[SQLExample]
```

List all SQL examples in the semantic catalog.

Retrieves all SQL examples stored in the semantic catalog.

**Arguments**:

- `con` - The database connection to the catalog database.
  

**Returns**:

  A list of SQLExample objects.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.search_sql_examples"></a>

#### search\_sql\_examples

```python
async def search_sql_examples(con: CatalogConnection,
                              embedding_name: str,
                              query: str | Sequence[float],
                              limit: int = 5) -> list[SQLExample]
```

Search for SQL examples using semantic search.

Performs a semantic search for SQL examples that match the query.
The query can be a natural language string or a vector embedding.

**Arguments**:

- `con` - The database connection to the catalog database.
- `embedding_name` - Name of the embedding configuration to use for the search.
- `query` - Natural language query string or vector embedding.
- `limit` - Maximum number of results to return.
  

**Returns**:

  A list of SQLExample objects ordered by similarity to the query.
  

**Raises**:

- `RuntimeError` - If the specified embedding configuration does not exist.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.list_facts"></a>

#### list\_facts

```python
async def list_facts(con: CatalogConnection) -> list[Fact]
```

List all facts in the semantic catalog.

Retrieves all facts stored in the semantic catalog.

**Arguments**:

- `con` - The database connection to the catalog database.
  

**Returns**:

  A list of Fact objects.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.search_facts"></a>

#### search\_facts

```python
async def search_facts(con: CatalogConnection,
                       embedding_name: str,
                       query: str | Sequence[float],
                       limit: int = 5) -> list[Fact]
```

Search for facts using semantic search.

Performs a semantic search for facts that match the query.
The query can be a natural language string or a vector embedding.

**Arguments**:

- `con` - The database connection to the catalog database.
- `embedding_name` - Name of the embedding configuration to use for the search.
- `query` - Natural language query string or vector embedding.
- `limit` - Maximum number of results to return.
  

**Returns**:

  A list of Fact objects ordered by similarity to the query.
  

**Raises**:

- `RuntimeError` - If the specified embedding configuration does not exist.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.load_objects"></a>

#### load\_objects

```python
async def load_objects(catalog_con: CatalogConnection,
                       target_con: TargetConnection,
                       obj_desc: list[ObjectDescription],
                       sample_size: int = 0) -> list[Table | View | Procedure]
```

Load database objects based on their descriptions.

Takes a list of object descriptions and loads the corresponding database objects
(tables, views, procedures) with their metadata. Matches the descriptions with
the loaded objects and attaches them. If sample_size is greater than 0, it also
retrieves sample data for tables and views.

**Arguments**:

- `catalog_con` - Connection to the semantic catalog database.
- `target_con` - Connection to the target database where the objects are defined.
- `obj_desc` - List of object descriptions to load.
- `sample_size` - Number of sample rows to retrieve from tables and views.
  If 0, no sample data is retrieved.
  

**Returns**:

  A list of database objects (Tables, Views, Procedures) with metadata and descriptions.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.render_objects"></a>

#### render\_objects

```python
def render_objects(objects: list[Table | View | Procedure]) -> str
```

Render database objects as SQL statements.

Renders tables, views, and procedures as SQL statements that can be used to
recreate them.

**Arguments**:

- `objects` - List of database objects to render.
  

**Returns**:

  A string containing the rendered SQL statements.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.render_sql_examples"></a>

#### render\_sql\_examples

```python
def render_sql_examples(sql_examples: list[SQLExample]) -> str
```

Render SQL examples as formatted text.

**Arguments**:

- `sql_examples` - List of SQL examples to render.
  

**Returns**:

  A string containing the rendered SQL examples.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.render_facts"></a>

#### render\_facts

```python
def render_facts(facts: list[Fact]) -> str
```

Render facts as formatted text.

**Arguments**:

- `facts` - List of facts to render.
  

**Returns**:

  A string containing the rendered facts.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.generate_sql"></a>

#### generate\_sql

```python
async def generate_sql(
        catalog_con: psycopg.AsyncConnection,
        target_con: psycopg.AsyncConnection,
        model: KnownModelName | Model,
        prompt: str,
        usage: Usage | None = None,
        usage_limits: UsageLimits | None = None,
        model_settings: ModelSettings | None = None,
        embedding_name: str | None = None,
        sample_size: int = 3,
        iteration_limit: int = 10,
        context_mode: ContextMode = "semantic_search",
        obj_ids: list[int] | None = None,
        sql_ids: list[int] | None = None,
        fact_ids: list[int] | None = None) -> GenerateSQLResponse
```

Generate a SQL statement based on a natural language prompt.

Uses AI to generate a SQL statement that fulfills the user's request, based on
context from the semantic catalog. The SQL is validated against the target database
to ensure it's correct.

**Arguments**:

- `catalog_con` - Connection to the semantic catalog database.
- `target_con` - Connection to the target database.
- `model` - AI model to use for generating SQL.
- `prompt` - Natural language prompt describing the desired SQL.
- `usage` - Optional usage tracking object.
- `usage_limits` - Optional usage limits.
- `model_settings` - Optional model settings.
- `embedding_name` - Name of the embedding to use for semantic search.
  If None, the first available embedding is used.
- `sample_size` - Number of sample rows to include in the context.
- `iteration_limit` - Maximum number of iterations for SQL refinement.
- `context_mode` - Mode for selecting context information ("semantic_search", "manual", etc.).
- `obj_ids` - Optional list of object IDs to include in the context (for "manual" mode).
- `sql_ids` - Optional list of SQL example IDs to include in the context (for "manual" mode).
- `fact_ids` - Optional list of fact IDs to include in the context (for "manual" mode).
  

**Returns**:

  A GenerateSQLResponse object containing the generated SQL and other information.
  

**Raises**:

- `RuntimeError` - If no embeddings are configured for the semantic catalog.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.import_catalog"></a>

#### import\_catalog

```python
async def import_catalog(catalog_con: psycopg.AsyncConnection,
                         target_con: psycopg.AsyncConnection,
                         yaml: TextIO,
                         embedding_name: str | None,
                         batch_size: int | None = None,
                         console: Console | None = None)
```

Import catalog items from a YAML file into the semantic catalog.

Reads catalog items (tables, views, procedures, SQL examples, facts) from a YAML file
and imports them into the semantic catalog. After importing, it generates vector
embeddings for the imported items using either all embedding configurations or
a specific one.

**Arguments**:

- `catalog_con` - Connection to the semantic catalog database.
- `target_con` - Connection to the target database.
- `yaml` - Text IO stream containing the YAML data to import.
- `embedding_name` - Optional name of the embedding configuration to use for vectorization.
  If None, all embedding configurations are used.
- `batch_size` - Number of items to process in each vectorization batch.
  If None, defaults to 32.
- `console` - Rich console for displaying progress information.
  If None, a default console is used.
  

**Raises**:

- `RuntimeError` - If the specified embedding configuration is not found.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.export_catalog"></a>

#### export\_catalog

```python
async def export_catalog(catalog_con: psycopg.AsyncConnection, yaml: TextIO)
```

Export the semantic catalog to a YAML file.

Exports all catalog items (tables, views, procedures, SQL examples, facts) from
the semantic catalog to a YAML file.

**Arguments**:

- `catalog_con` - Connection to the semantic catalog database.
- `yaml` - Text IO stream to write the YAML data to.

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.fix_ids"></a>

#### fix\_ids

```python
async def fix_ids(catalog_con: psycopg.AsyncConnection,
                  target_con: psycopg.AsyncConnection,
                  dry_run: bool = False,
                  console: Console | None = None)
```

Fix internal PostgreSQL IDs in the semantic catalog.

Database objects like tables, views, or columns can have their internal IDs changed
when database operations occur (like dumps/restores or migrations). This method
fixes the internal IDs stored in the semantic catalog to match the current
values in the target database.

For each object in the semantic catalog:
- If the object no longer exists in the target database, it will be deleted
- If the object's IDs don't match the current values, they will be updated
- If the object's IDs already match, it will be left unchanged

**Arguments**:

- `catalog_con` - Connection to the database containing the semantic catalog
- `target_con` - Connection to the target database containing the actual objects
- `dry_run` - If True, only check for issues without making changes
- `console` - Rich console for output and progress display. If None, a default
  console with minimal output is used

<a id="pgai.semantic_catalog.semantic_catalog.SemanticCatalog.fix_names"></a>

#### fix\_names

```python
async def fix_names(catalog_con: psycopg.AsyncConnection,
                    target_con: psycopg.AsyncConnection,
                    dry_run: bool = False,
                    console: Console | None = None)
```

Fix object name identifiers in the semantic catalog.

Database objects like tables, views, or columns can have their names changed
when database operations occur (like renames or schema changes). This method
fixes the name identifiers stored in the semantic catalog to match the current
values in the target database.

For each object in the semantic catalog:
- If the object no longer exists in the target database, it will be deleted
- If the object's name identifiers don't match the current values, they will be updated
- If the object's name identifiers already match, it will be left unchanged

**Arguments**:

- `catalog_con` - Connection to the database containing the semantic catalog
- `target_con` - Connection to the target database containing the actual objects
- `dry_run` - If True, only check for issues without making changes
- `console` - Rich console for output and progress display. If None, a default
  console with minimal output is used

<a id="pgai.semantic_catalog.semantic_catalog.from_id"></a>

#### from\_id

```python
async def from_id(con: CatalogConnection, id: int) -> SemanticCatalog
```

Get a semantic catalog by its ID.

Retrieves a semantic catalog from the database using its unique identifier.

**Arguments**:

- `con` - Connection to the catalog database.
- `id` - The unique identifier of the semantic catalog to retrieve.
  

**Returns**:

  A SemanticCatalog instance representing the semantic catalog.
  

**Raises**:

- `RuntimeError` - If the semantic catalog is not installed or the specified ID is not found.

<a id="pgai.semantic_catalog.semantic_catalog.from_name"></a>

#### from\_name

```python
async def from_name(con: CatalogConnection,
                    catalog_name: str) -> SemanticCatalog
```

Get a semantic catalog by its name.

Retrieves a semantic catalog from the database using its name.

**Arguments**:

- `con` - Connection to the catalog database.
- `catalog_name` - The name of the semantic catalog to retrieve.
  

**Returns**:

  A SemanticCatalog instance representing the semantic catalog.
  

**Raises**:

- `RuntimeError` - If the semantic catalog is not installed or the specified name is not found.

<a id="pgai.semantic_catalog.semantic_catalog.list_semantic_catalogs"></a>

#### list\_semantic\_catalogs

```python
async def list_semantic_catalogs(
        con: CatalogConnection) -> list[SemanticCatalog]
```

List all semantic catalogs in the database.

Retrieves all semantic catalogs defined in the database.

**Arguments**:

- `con` - Connection to the catalog database.
  

**Returns**:

  A list of SemanticCatalog instances representing all semantic catalogs.
  

**Raises**:

- `RuntimeError` - If the semantic catalog is not installed.

<a id="pgai.semantic_catalog.semantic_catalog.create"></a>

#### create

```python
async def create(
        con: CatalogConnection,
        catalog_name: str | None = None,
        embedding_name: str | None = None,
        embedding_config: EmbeddingConfig | None = None) -> SemanticCatalog
```

Create a new semantic catalog in the database.

Creates a new semantic catalog with optional embedding configuration.

**Arguments**:

- `con` - Connection to the catalog database.
- `catalog_name` - Optional name for the semantic catalog. If not provided,
  a default name will be generated.
- `embedding_name` - Optional name for the embedding configuration. If not provided,
  a default name will be generated.
- `embedding_config` - Optional embedding configuration to add to the semantic catalog.
  

**Returns**:

  A SemanticCatalog instance representing the newly created semantic catalog.
  

**Raises**:

- `RuntimeError` - If the semantic catalog could not be created.

