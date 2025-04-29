# Alembic integration

Alembic is a database migration tool that allows you to manage your database schema. This document describes how to use Alembic to manage your vectorizer definitions, since those should be considered part of your database schema. 

We first cover how to create vectorizers using the Alembic operations. Then, we cover how to exclude the tables created and managed by pgai Vectorizer from the autogenerate process.

## Creating vectorizers
pgai provides native Alembic operations for managing vectorizers. For them to work you need to run `register_operations` in your env.py file. Which registers the pgai operations under the global op context:

```python
from pgai.alembic import register_operations

register_operations()
```

Then you can use the `create_vectorizer` operation to create a vectorizer for your model. As well as the `drop_vectorizer` operation to remove it.

```python
from alembic import op
from pgai.vectorizer.configuration import (
    EmbeddingOpenaiConfig,
    ChunkingCharacterTextSplitterConfig,
    FormattingPythonTemplateConfig,
    LoadingColumnConfig,
    DestinationTableConfig
)


def upgrade() -> None:
    op.create_vectorizer(
        source="blog",
        name="blog_content_embedder",  # Optional custom name for easier reference
        destination=DestinationTableConfig(
            destination='blog_embeddings'
        )
        loading=LoadingColumnConfig(column_name='content'),
        embedding=EmbeddingOpenaiConfig(
            model='text-embedding-3-small',
            dimensions=768
        ),
        chunking=ChunkingCharacterTextSplitterConfig(
            chunk_size=800,
            chunk_overlap=400,
            separator='.',
            is_separator_regex=False
        ),
        formatting=FormattingPythonTemplateConfig(template='$title - $chunk')
    )


def downgrade() -> None:
    op.drop_vectorizer(name="blog_content_embedder", drop_all=True)
```

The `create_vectorizer` operation supports all configuration options available in the [SQL API](/docs/vectorizer/api-reference.md).

## Excluding tables created by pgai Vectorizer from Alembic autogeneration

When you create a vectorizer, pgai automatically creates a table to store the vector embeddings. This table is managed by pgai and should not be included in created by alembic migrations. So, if you are using alembic's autogenerate functionality to generate migrations, you will need to exclude these tables from the autogenerate process.

If you are using SQLAlchemy, the `vectorizer_relationship` generates a new SQLAlchemy model, that is available under the attribute that you specify, and those models need to be excluded from the autogenerate process. When those models are created, they are added to a list in your metadata called `pgai_managed_tables` and you can exclude them by adding the following to your `env.py`:

```python
def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name in target_metadata.info.get("pgai_managed_tables", set()):
        return False
    return True

context.configure(
      connection=connection,
      target_metadata=target_metadata,
      include_object=include_object
  )
```

This should now prevent alembic from generating tables for these models when you run `alembic revision --autogenerate`.
