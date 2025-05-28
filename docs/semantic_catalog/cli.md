# Semantic Catalog CLI Reference

The pgai semantic catalog feature provides a comprehensive command-line interface for managing semantic catalogs that enable natural language to SQL functionality. This document provides detailed information about each CLI command, their usage, and their purpose in the text-to-SQL workflow.

## Overview

The semantic catalog CLI commands are accessed through the `pgai semantic-catalog` command group. Each command serves a specific purpose in the workflow of creating, managing, and using semantic catalogs for natural language database interactions.

### Basic Workflow

1. **Describe** - Generate natural language descriptions of database objects
2. **Create** - Create a new semantic catalog with embedding configuration
3. **Import** - Import descriptions into the semantic catalog
4. **Vectorize** - Generate embeddings for semantic search capabilities
5. **Search** - Perform semantic searches to find relevant database objects
6. **Generate SQL** - Generate SQL statements from natural language prompts


## Database Connections

A semantic catalog is used to describe and generate SQL for a postgres database.
The semantic catalog itself is also stored in a postgres database. It can be
colocated with the database being described, or it can be stored in a separate
database.

We refer to the database being described as the `target database`. We use the `-d`
or `--db-url` argument or the `TARGET_DB` environment variable to specify this
postgres connection string.

The database containing the semantic catalog is the `catalog database`. We use the `-c`
or `--catalog-db-url` argument or the `CATALOG_DB` environment variable to specify
this postgres connection string.

Some commands only need a connection to one database or the other. 
Some commands need a connection to both databases.

If you store the semantic catalog in the target database, you can specify just
the target database connection string (`-d`, `--db-url` or `TARGET_DB`) and omit
the catalog database connection string.

## Commands

### `pgai semantic-catalog describe`

**Purpose**: Automatically generate natural language descriptions for database objects using AI.

This command connects to a database, analyzes its schema, and uses a large language model to create human-readable descriptions of tables, views, procedures, and other database objects. These descriptions form the foundation of your semantic catalog.

The command creates or appends to a YAML file. You may review and edit the descriptions. The file can be imported into a semantic catalog with the `import` command.

#### Usage

```bash
pgai semantic-catalog describe [OPTIONS]
```

#### Key Options

| Option | Description | Default | Environment Variable |
|--------|-------------|---------|---------------------|
| `-d, --db-url` | Database connection URL | Required | `TARGET_DB` |
| `-m, --model` | LLM model for generating descriptions | `openai:gpt-4.1` | |
| `-f, --yaml-file` | Output YAML file path | stdout | |
| `--include-schema` | Regex pattern to include schemas | | |
| `--exclude-schema` | Regex pattern to exclude schemas | | |
| `--include-table` | Regex pattern to include tables | | |
| `--exclude-table` | Regex pattern to exclude tables | | |
| `--include-view` | Regex pattern to include views | | |
| `--exclude-view` | Regex pattern to exclude views | | |
| `--include-proc` | Regex pattern to include procedures | | |
| `--exclude-proc` | Regex pattern to exclude procedures | | |
| `--include-extension` | Extension names to include objects from | | |
| `-a, --append` | Append to output file instead of overwriting | `false` | |
| `--sample-size` | Number of sample rows per table/view | `3` | |
| `--batch-size` | Objects to process per LLM request | `5` | |
| `--request-limit` | Maximum LLM requests (cost control) | | |
| `--total-tokens-limit` | Maximum LLM tokens (cost control) | | |
| `--dry-run` | List objects without describing them | `false` | |
| `-q, --quiet` | Suppress progress messages | `false` | |

#### Examples

```bash
# Generate descriptions for all objects in a database
pgai semantic-catalog describe -f descriptions.yaml

# Only include specific schemas and exclude system objects
pgai semantic-catalog describe \
  --include-schema "public|app_.*" \
  --exclude-schema "pg_.*|information_schema" \
  -f descriptions.yaml

# Use a different model with cost controls
pgai semantic-catalog describe \
  --model anthropic:claude-3-sonnet-20240229 \
  --request-limit 100 \
  --total-tokens-limit 50000 \
  -f descriptions.yaml

# Dry run to see what would be processed
pgai semantic-catalog describe --dry-run
```

#### When to Use

- Starting a new text-to-SQL project with an existing database
- Adding new database objects that need descriptions
- Refreshing descriptions after significant schema changes
- Creating documentation for database objects

---

### `pgai semantic-catalog create`

**Purpose**: Create a new semantic catalog with an embedding configuration.

This command initializes a semantic catalog in your database and sets up the necessary embedding configuration for generating vector embeddings. The catalog requires at least one embedding configuration to enable semantic search.

#### Usage

```bash
pgai semantic-catalog create [OPTIONS]
```

#### Key Options

| Option | Description | Default | Environment Variable |
|--------|-------------|---------|---------------------|
| `-c, --catalog-db-url` | Catalog database connection URL | | `CATALOG_DB` or `TARGET_DB` |
| `-n, --catalog-name` | Name for the semantic catalog | `default` | |
| `-e, --embed-config` | Name for the embedding configuration | | |
| `-p, --provider` | Embedding provider | `openai` | |
| `-m, --model` | Embedding model | `text-embedding-3-small` | |
| `-v, --vector-dimensions` | Vector dimensions | `1536` | |
| `--base-url` | Custom base URL for embedding provider | | |
| `--api-key-name` | Environment variable containing API key | | |

#### Supported Providers and Models

**OpenAI** (requires API key):
- `text-embedding-3-small` (1536 dimensions)
- `text-embedding-3-large` (3072 dimensions)
- `text-embedding-ada-002` (1536 dimensions)

**Ollama** (local inference):
- `nomic-embed-text`
- `mxbai-embed-large`
- Any embedding model available in your Ollama instance

**Sentence Transformers** (local inference):
- `all-MiniLM-L6-v2`
- `all-mpnet-base-v2`
- Any model from Hugging Face sentence-transformers

#### Examples

```bash
# Create a catalog with OpenAI embeddings (default)
pgai semantic-catalog create

# Create a catalog with custom name and embedding configuration
pgai semantic-catalog create \
  --catalog-name "production_catalog" \
  --embed-config "openai_embeddings"

# Create a catalog with Ollama (local model)
pgai semantic-catalog create \
  --provider ollama \
  --model nomic-embed-text \
  --vector-dimensions 768

# Create a catalog with custom OpenAI base URL
pgai semantic-catalog create \
  --provider openai \
  --base-url "https://api.openai.com/v1" \
  --api-key-name "CUSTOM_OPENAI_KEY"
```

#### When to Use

- Setting up your first semantic catalog
- Creating separate catalogs for different environments (dev, staging, prod)
- Setting up A/B testing with different embedding configurations
- Migrating to a new embedding provider or model

---

### `pgai semantic-catalog import`

**Purpose**: Import database object descriptions from a YAML file into a semantic catalog.

This command reads descriptions (typically generated by the `describe` command) from a YAML file and loads them into your semantic catalog. After importing, it will automatically generate embeddings for the imported items.

#### Usage

```bash
pgai semantic-catalog import [OPTIONS]
```

#### Key Options

| Option | Description                          | Default | Environment Variable |
|--------|--------------------------------------|---------|---------------------|
| `-d, --db-url` | Target database connection URL       | Required | `TARGET_DB` |
| `-c, --catalog-db-url` | Catalog database connection URL      | | `CATALOG_DB` |
| `-f, --yaml-file` | Input YAML file path                 | stdin | |
| `-n, --catalog-name` | Semantic catalog name                | `default` | |
| `-e, --embed-config` | Embedding configuration to vectorize | All configs | |
| `-b, --batch-size` | Embeddings per batch                 | | |

#### Examples

```bash
# Import from a YAML file
pgai semantic-catalog import -f descriptions.yaml

# Import to a specific catalog and vectorize only a specific embedding config
pgai semantic-catalog import \
  -f descriptions.yaml \
  --catalog-name "my_catalog" \
  --embed-config "openai_embeddings"

# Import from stdin
cat descriptions.yaml | pgai semantic-catalog import

# Import with custom batch size for vectorization
pgai semantic-catalog import \
  -f descriptions.yaml \
  --batch-size 16
```

#### When to Use

- Loading initial descriptions into a new semantic catalog
- Updating descriptions after running the `describe` command
- Migrating descriptions between environments
- Restoring a semantic catalog from backup

---

### `pgai semantic-catalog vectorize`

**Purpose**: Generate vector embeddings for items in the semantic catalog.

This command processes database objects, SQL examples, and facts in your semantic catalog that don't yet have embeddings and generates vector representations using your configured embedding provider. These embeddings enable semantic search capabilities.

#### Usage

```bash
pgai semantic-catalog vectorize [OPTIONS]
```

#### Key Options

| Option | Description | Default | Environment Variable |
|--------|-------------|---------|---------------------|
| `-c, --catalog-db-url` | Catalog database connection URL | | `CATALOG_DB` or `TARGET_DB` |
| `-n, --catalog-name` | Semantic catalog name | `default` | |
| `-e, --embed-config` | Embedding configuration to use | All configs | |
| `-b, --batch-size` | Items per vectorization batch | `32` | |

#### Examples

```bash
# Vectorize all items using all embedding configurations
pgai semantic-catalog vectorize

# Vectorize using a specific embedding configuration
pgai semantic-catalog vectorize --embed-config "openai_embeddings"

# Vectorize with custom batch size
pgai semantic-catalog vectorize --batch-size 16

# Vectorize a specific catalog
pgai semantic-catalog vectorize --catalog-name "production_catalog"
```

#### When to Use

- After importing new descriptions into the catalog
- When adding a new embedding configuration to existing data
- Regenerating embeddings after model updates
- Processing items that failed during initial vectorization

---

### `pgai semantic-catalog search`

**Purpose**: Search the semantic catalog using natural language queries.

This command performs semantic search across database objects, SQL examples, and facts using natural language. It's useful for exploring your database schema, finding relevant examples, and understanding what data is available.

#### Usage

```bash
pgai semantic-catalog search [OPTIONS]
```

#### Key Options

| Option | Description | Default | Environment Variable |
|--------|-------------|---------|---------------------|
| `-d, --db-url` | Target database connection URL | Required | `TARGET_DB` |
| `-c, --catalog-db-url` | Catalog database connection URL | | `CATALOG_DB` |
| `-n, --catalog-name` | Semantic catalog name | `default` | |
| `-e, --embed-config` | Embedding configuration to use | First available | |
| `-p, --prompt` | Natural language search query | Required | |
| `-s, --sample-size` | Sample rows per table/view | `3` | |
| `--render` | Show formatted results for LLM prompts | `false` | |

#### Examples

```bash
# Search for user-related objects
pgai semantic-catalog search --prompt "user accounts and profiles"

# Search with specific question
pgai semantic-catalog search --prompt "How are orders related to customers?"

# Search and see how results would be rendered for LLM
pgai semantic-catalog search \
  --prompt "product inventory and stock levels" \
  --render

# Search with more sample data
pgai semantic-catalog search \
  --prompt "sales data" \
  --sample-size 5
```

#### When to Use

- Exploring unfamiliar database schemas
- Finding relevant tables for a specific business question
- Discovering existing SQL examples for similar queries
- Understanding relationships between database objects
- Testing the quality of your semantic catalog

---

### `pgai semantic-catalog generate-sql`

**Purpose**: Generate SQL statements from natural language prompts using the semantic catalog.

This is the primary command for text-to-SQL functionality. It uses the semantic catalog to find relevant context and generates SQL statements that answer your natural language questions.

#### Usage

```bash
pgai semantic-catalog generate-sql [OPTIONS]
```

#### Key Options

| Option | Description | Default | Environment Variable |
|--------|-------------|---------|---------------------|
| `-d, --db-url` | Target database connection URL | Required | `TARGET_DB` |
| `-c, --catalog-db-url` | Catalog database connection URL | | `CATALOG_DB` |
| `-m, --model` | LLM model for SQL generation | `openai:gpt-4.1` | |
| `-n, --catalog-name` | Semantic catalog name | `default` | |
| `-e, --embed-config` | Embedding configuration to use | First available | |
| `-p, --prompt` | Natural language query | Required | |
| `--iteration-limit` | Maximum refinement attempts | `5` | |
| `-s, --sample-size` | Sample rows per table/view | `3` | |
| `--request-limit` | Maximum LLM requests | | |
| `--total-tokens-limit` | Maximum LLM tokens | | |
| `--print-messages` | Show LLM conversation | `false` | |
| `--print-usage` | Show token usage | `false` | |
| `--print-query-plan` | Show query execution plan | `false` | |
| `--save-final-prompt` | Save final LLM prompt to file | | |

#### Examples

```bash
# Generate SQL for a simple question
pgai semantic-catalog generate-sql \
  --prompt "Find all users who signed up last month"

# Use a specific model with debugging enabled
pgai semantic-catalog generate-sql \
  --model "anthropic:claude-3-opus-20240229" \
  --prompt "What are the top 5 products by revenue?" \
  --print-usage \
  --print-messages

# Generate SQL with cost controls
pgai semantic-catalog generate-sql \
  --prompt "Show customer order history" \
  --request-limit 10 \
  --total-tokens-limit 20000

# Save the final prompt for analysis
pgai semantic-catalog generate-sql \
  --prompt "Find inactive customers" \
  --save-final-prompt debug_prompt.txt
```

#### When to Use

- Converting business questions to SQL queries
- Exploring data through natural language
- Rapid prototyping of data analysis queries
- Training and education on database querying
- Building natural language interfaces to your database

---

### `pgai semantic-catalog export`

**Purpose**: Export semantic catalog contents to a YAML file.

This command exports all database objects, SQL examples, and facts from a semantic catalog to a YAML file. This is useful for backups, migration between environments, or editing catalog contents (file can be subsequently imported).

#### Usage

```bash
pgai semantic-catalog export [OPTIONS]
```

#### Key Options

| Option | Description | Default | Environment Variable |
|--------|-------------|---------|---------------------|
| `-c, --catalog-db-url` | Catalog database connection URL | | `CATALOG_DB` or `TARGET_DB` |
| `-f, --yaml-file` | Output YAML file path | stdout | |
| `-n, --catalog-name` | Semantic catalog name | `default` | |

#### Examples

```bash
# Export to a YAML file
pgai semantic-catalog export -f catalog_backup.yaml

# Export a specific catalog
pgai semantic-catalog export \
  --catalog-name "production_catalog" \
  -f production_backup.yaml

# Export to stdout and pipe to another command
pgai semantic-catalog export | gzip > catalog_backup.yaml.gz
```

#### When to Use

- Creating backups of semantic catalogs
- Migrating catalogs between environments
- Sharing catalog contents with team members
- Version controlling semantic catalog contents

---

### `pgai semantic-catalog fix`

**Purpose**: Fix database object references in the semantic catalog after database changes.

When database operations like dumps/restores, renames, or schema changes occur, the internal references in your semantic catalog may become outdated. This command updates these references to maintain accuracy.

#### Usage

```bash
pgai semantic-catalog fix [OPTIONS]
```

#### Key Options

| Option | Description | Default |
|--------|-------------|---------|
| `-d, --db-url` | Target database connection URL | Required |
| `-c, --catalog-db-url` | Catalog database connection URL | |
| `-n, --catalog-name` | Semantic catalog name | `default` |
| `-m, --mode` | Fix mode: `fix-ids` or `fix-names` | `fix-ids` |
| `--dry-run` | Show what would be changed | `false` |

#### Fix Modes

**fix-ids**: Updates internal PostgreSQL object IDs
- Use after database dumps/restores
- Use after major schema changes
- Updates classid, objid, objsubid references

**fix-names**: Updates object name identifiers
- Use after object renames
- Use after schema renames
- Updates objnames arrays

#### Examples

```bash
# Fix internal IDs after database restore
pgai semantic-catalog fix --mode fix-ids

# Fix object names after renames
pgai semantic-catalog fix --mode fix-names

# Dry run to see what would be fixed
pgai semantic-catalog fix --mode fix-ids --dry-run

# Fix a specific catalog
pgai semantic-catalog fix \
  --catalog-name "production_catalog" \
  --mode fix-names
```

#### When to Use

- After database dumps and restores
- After renaming database objects or schemas
- When semantic catalog searches return incorrect results
- After major database schema changes
- When object references become stale

## Best Practices

### 1. Development Workflow

```bash
# 1. Generate descriptions
pgai semantic-catalog describe -f descriptions.yaml

# 2. Review and edit descriptions.yaml if needed

# 3. Create catalog
pgai semantic-catalog create

# 4. Import descriptions
pgai semantic-catalog import -f descriptions.yaml

# 5. Test search functionality
pgai semantic-catalog search --prompt "your test query"

# 6. Generate SQL
pgai semantic-catalog generate-sql --prompt "your business question"
```

### 2. Production Deployment

```bash
# Use separate catalog database
export CATALOG_DB="postgres://user:pass@catalog-host:5432/catalog_db"
export TARGET_DB="postgres://user:pass@app-host:5432/app_db"

# Create named catalog with specific embedding config
pgai semantic-catalog create \
  --catalog-name "production" \
  --embed-config "production_embeddings"

# Import
pgai semantic-catalog import \
  -f descriptions.yaml \
  --catalog-name "production"
```

### 3. Maintenance

```bash
# Regular backup
pgai semantic-catalog export \
  --catalog-name "production" \
  -f "backup-$(date +%Y%m%d).yaml"

# After database changes
pgai semantic-catalog fix --mode fix-ids

# Update descriptions periodically
pgai semantic-catalog describe -f new_descriptions.yaml
pgai semantic-catalog import -f new_descriptions.yaml
```

## Troubleshooting

### Common Issues

**"No embedding configuration found"**
- Run `pgai semantic-catalog create` to set up embedding configuration
- Check that the catalog name and embedding config name are correct

**"Connection refused"**
- Verify database URLs are correct
- Ensure databases are running and accessible
- Check authentication credentials

**"API key not found"**
- Set the appropriate environment variable (e.g., `OPENAI_API_KEY`)
- Use `--api-key-name` to specify custom environment variable

**"Object not found" after database restore**
- Run `pgai semantic-catalog fix --mode fix-ids` to update object references

**Poor SQL generation quality**
- Review and improve object descriptions in YAML files
- Add more SQL Examples and/or Facts to the catalog
- Use higher quality embedding models
- Use a more powerful LLM model
- Increase sample size for more context

### Getting Help

Use the `--help` flag with any command for detailed option information:

```bash
pgai semantic-catalog --help
pgai semantic-catalog describe --help
pgai semantic-catalog generate-sql --help
```