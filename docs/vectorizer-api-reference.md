
# pgai Vectorizer API reference

This page provides an API reference for Vectorizer functions. For an overview
of Vectorizer and how it works, see the [Vectorizer Guide](./vectorizer.md).

A vectorizer provides you with a powerful and automated way to generate and 
manage LLM embeddings for your PostgreSQL data. Here's a summary of what you 
gain from Vectorizers:

- **Automated embedding generation**: you can create a vectorizer for a specified
   table, which automatically generates embeddings for the data in that table and
   keeps them in sync with the source data.

- **Automatic synchronization**: a vectorizer creates triggers on the source table, 
   ensuring that embeddings are automatically updated when the source data 
   changes.
   
- **Background processing**: the process to create embeddings runs
asynchrounously in the background. This minimizes the impact on regular database
operations such as INSERT, UPDATE, and DELETE.
  
- **Scalability**: a vectorizer processes data in batches and can run concurrently. 
  This enables vectorizers to handle large datasets efficiently.

- **Configurable embedding process**: a vectorizer is highly configurable, 
   allowing you to specify:
    - The embedding model and dimensions. For example, the `nomic-embed-text` model in Ollama.
    - Chunking strategies for text data.
    - Formatting templates for combining multiple fields.
    - Indexing options for efficient similarity searches.
    - Scheduling for background processing.

- **Integration with multiple AI providers**: a vectorizer supports different 
   embedding providers, initially including OpenAI, with more planned for the 
   future.

- **Efficient storage and retrieval**: embeddings are stored in a separate table 
   with appropriate indexing, optimizing for vector similarity searches.

- **View creation**: a view is automatically created to join the original data with
   its embeddings, making it easy to query and use the embedded data.

- **Fine-grained access control**: you can specify the roles that have 
   access to a vectorizer and its related objects.

- **Monitoring and management**:  monitor the vectorizer's queue, enable/disable scheduling, and manage the vectorizer 
  lifecycle.

Vectorizer significantly simplifies the process of incorporating AI-powered 
semantic search and analysis capabilities into existing PostgreSQL databases.  
Making it easier for you to leverage the power of LLMs in your data workflows.

Vectorizers are available on [Timescale Cloud][timescale-cloud]. You can
also run it yourself, please see the [Self Hosting Guide](TODO).

Vectorizer offers the following APIs:

**Create and configure vectorizers**
- [Create vectorizers](#create-vectorizers): automate the process of creating embeddings for table data.
- [Chunking configuration](#chunking-configuration): define the way text data is split into smaller, manageable pieces 
  before being processed for embeddings.
- [Embedding configuration](#embedding-configuration): specify the LLM provider, model, and the parameters to be
  used when generating the embeddings
- [Formatting configuration](#formatting-configuration): configure the way data from the source table is formatted
  before it is sent for embedding.
- [Indexing configuration](#indexing-configuration): specify the way generated embeddings should be indexed for 
  efficient similarity searches.
- [Scheduling configuration](#scheduling-configuration): configure when and how often the vectorizer should run in order 
  to process new or updated data.
- [Processing configuration](#processing-configuration): specify the way the vectorizer should process data when 
  generating embeddings.

**Manage vectorizers**
- [Enable and disable vectorizer schedules](#enable-and-disable-vectorizer-schedules): temporarily pause or resume the 
  automatic processing of embeddings, without having to delete or recreate the vectorizer configuration.
- [Drop a vectorizer](#drop-a-vectorizer): remove a vectorizer that you created previously, and clean up the associated
  resources.

**Monitor vectorizers**
- [View vectorizer status](#view-vectorizer-status): monitoring tools in pgai that provide insights into the state and 
  performance of vectorizers.


## Create vectorizers

You use the `ai.create_vectorizer` function in pgai to set up and configure an automated system 
for generating and managing embeddings for a specific table in your database.

The purpose of `ai.create_vectorizer` is to:
- Automate the process of creating embeddings for table data.
- Set up necessary infrastructure such as tables, views, and triggers for embedding management.
- Configure the embedding generation process according to user specifications.
- Integrate with AI providers for embedding creation.
- Set up scheduling for background processing of embeddings.

### Example usage

By using `ai.create_vectorizer`, you can quickly set up a sophisticated
embedding system tailored to your specific needs, without having to manually
create and manage all the necessary database objects and processes. For example:

```sql
SELECT ai.create_vectorizer(
    'website.blog'::regclass,
    embedding => ai.embedding_ollama('nomic-embed-text', 768),
    chunking => ai.chunking_character_text_splitter('body', 128, 10),
    formatting => ai.formatting_python_template('title: $title published: $published $chunk'),
    grant_to => ai.grant_to('bob', 'alice')
);
```

This function call:
1. Sets up a vectorizer for the `website.blog` table.
2. Uses the Ollama `nomic-embed-text` model to create 768 dimensional embeddings.
3. Chunks the `body` column into 128-character pieces with a 10-character overlap.
4. Formats each chunk with a `title` and a `published` date.
5. Grants necessary permissions to the roles `bob` and `alice`.

The function returns an integer identifier for the vectorizer created, which you can use
in other management functions.

### Parameters

`ai.create_vectorizer` takes the following parameters:

| Name             | Type                                                   | Default                           | Required | Description                                                                                        |
|------------------|--------------------------------------------------------|-----------------------------------|----------|----------------------------------------------------------------------------------------------------|
| source           | regclass                                               | -                                 | ✔        | The source table that embeddings are generated for.                                                |
| destination      | name                                                   | -                                 | ✖        | Set the name of the table embeddings are stored in, and the view with both the original data and the embeddings.<br>The view is named `<destination>`, the embedding table is named `<destination>_store`.<br>You set destination to avoid naming conflicts when you configure additional vectorizers for a source table.                              |
| embedding        | [Embedding configuration](#embedding-configuration)    | -                                 | ✔        | Set how to embed the data.                                                                         |
| chunking         | [Chunking configuration](#chunking-configuration)      | -                                 | ✔        | Set the way to split text data, using functions like `ai.chunking_character_text_splitter()`.      |
| indexing         | [Indexing configuration](#indexing-configuration)      | `ai.indexing_default()`           | ✖        | Specify how to index the embeddings. For example, `ai.indexing_diskann()` or `ai.indexing_hnsw()`. |
| formatting       | [Formatting configuration](#formatting-configuration)  | `ai.formatting_python_template()` | ✖        | Define the data format before embedding, using `ai.formatting_python_template()`.                  |
| scheduling       | [Scheduling configuration](#scheduling-configuration)  | `ai.scheduling_default()`         | ✖        | Set how often to run the vectorizer. For example, `ai.scheduling_timescaledb()`.                   |
| processing       | [Processing configuration](#processing-configuration ) | `ai.processing_default()`         | ✖        | Configure the way to process the embeddings.                                                       |
| target_schema    | name                                                   | -                                 | ✖        | Specify the schema where the embeddings will be stored. This argument takes precedence over `destination`.                                     |
| target_table     | name                                                   | -                                 | ✖        | Specify name of the table where the embeddings will be stored.                                     |
| view_schema      | name                                                   | -                                 | ✖        | Specify the schema where the view is created.                                                      |
| view_name        | name                                                   | -                                 | ✖        | Specify the name of the view to be created. This argument takes precedence over `destination`.                                     |
| queue_schema     | name                                                   | -                                 | ✖        | Specify the schema where the work queue table is created.                                         |
| queue_table      | name                                                   | -                                 | ✖        | Specify the name of the work queue table.                                                          |
| grant_to         | [Grant To configuration][#grant-to-configuration]      | `ai.grant_to_default()`           | ✖        | Specify which users should be able to use objects created by the vectorizer.                       |
| enqueue_existing | bool                                                   | `true`                            | ✖        | Set to `true` if existing rows should be immediately queued for embedding.                         |


#### Returns

The `int` id of the vectorizer that you created.

## Chunking configuration

You use the chunking configuration functions in `pgai` to define the way text data is split into smaller, 
manageable pieces before being processed for embeddings. This is crucial because many embedding models have input size 
limitations, and chunking allows for processing of larger text documents while maintaining context.

By using chunking functions, you can fine-tune how your text data is
prepared for embedding, ensuring that the chunks are appropriately sized and
maintain necessary context for their specific use case. This is particularly
important for maintaining the quality and relevance of the generated embeddings,
especially when dealing with long-form content or documents with specific
structural elements.

The chunking functions are:

- [ai.chunking_character_text_splitter](#aichunking_character_text_splitter)
- [ai.chunking_recursive_character_text_splitter](#aichunking_recursive_character_text_splitter)

The key difference between these functions is that `chunking_recursive_character_text_splitter`
allows for a more sophisticated splitting strategy, potentially preserving more
semantic meaning in the chunks.

### ai.chunking_character_text_splitter

You use `ai.chunking_character_text_splitter` to:
- Split text into chunks based on a specified separator.
- Control the chunk size and the amount of overlap between chunks.

#### Example usage

- Split the `body` column of the `my_table` table into chunks of 128 characters, with 10
  character overlap, using '\n;' as the separator:

  ```sql
  SELECT ai.create_vectorizer(
      'my_table'::regclass,
      chunking => ai.chunking_character_text_splitter('body', 128, 10, E'\n'),
      -- other parameters...
  );
  ```

#### Parameters

`ai.chunking_character_text_splitter` takes the following parameters:

|Name| Type | Default | Required | Description                                            |
|-|------|---------|-|--------------------------------------------------------|
|chunk_column| name | -       |✔| The name of the column containing the text to be chunked |
|chunk_size| int  | 800     |✖| The maximum number of characters in a chunk            |
|chunk_overlap| int  | 400     |✖| The number of characters to overlap between chunks     |
|separator| text | E'\n\n' |✖| The string or character used to split the text         |
|is_separator_regex| bool | false   |✖| Set to `true` if `separator` is a regular expression. |

#### Returns

A JSON configuration object that you can use in [ai.create_vectorizer](#create-vectorizers).

### ai.chunking_recursive_character_text_splitter

`ai.chunking_recursive_character_text_splitter` provides more fine-grained control over the chunking process. 
You use it to recursively split text into chunks using multiple separators.

#### Example usage

- Recursively split the `content` column into chunks of 256 characters, with a 20 character 
  overlap, first trying to split on '\n;', then on spaces:

  ```sql
    SELECT ai.create_vectorizer(
      'my_table'::regclass,
      chunking => ai.chunking_recursive_character_text_splitter(
        'content', 
        256, 
        20, 
        separators => array[E'\n;', ' ']
      ),
      -- other parameters...
  );
  ```

#### Parameters

`ai.chunking_recursive_character_text_splitter` takes the following parameters:

| Name               | Type | Default | Required | Description                                              |
|--------------------|------|---------|-|----------------------------------------------------------|
| chunk_column       | name | -       |✔| The name of the column containing the text to be chunked |
| chunk_size         | int  | 800     |✖| The maximum number of characters per chunk               |
| chunk_overlap      | int  | 400     |✖| The number of characters to overlap between chunks       |
| separators         | text[] | array[E'\n\n', E'\n', '.', '?', '!', ' ', ''] |✖| The string or character used to split the text |
| is_separator_regex | bool | false   |✖| Set to `true` if `separator` is a regular expression. |

#### Returns

A JSON configuration object that you can use in [ai.create_vectorizer](#create-vectorizers).

## Embedding configuration

You use the embedding configuration functions to specify how embeddings are
generated for your data.

The embedding functions are:

- [ai.embedding_openai](#aiembedding_openai)
- [ai.embedding_ollama](#aiembedding_ollama)
- [ai.embedding_voyageai](#aiembedding_voyageai)

### ai.embedding_openai

You call the `ai.embedding_openai` function to use an OpenAI model to generate embeddings.

The purpose of `ai.embedding_openai` is to:
- Define which OpenAI embedding model to use.
- Specify the dimensionality of the embeddings.
- Configure optional parameters like the user identifier for API calls.
- Set the name of the [environment variable that holds the value of your OpenAI API key][openai-use-env-var].  

#### Example usage

Use `ai.embedding_openai` to create an embedding configuration object that is passed as an argument to [ai.create_vectorizer](#create-vectorizers):

1. Set the value of your OpenAI API key.

   For example, [in an environment variable][openai-set-key] or in a [Docker configuration][docker configuration].
   
2. Create a vectorizer with OpenAI as the embedding provider: 

    ```sql
    SELECT ai.create_vectorizer(
        'my_table'::regclass,
        embedding => ai.embedding_openai(
          'text-embedding-3-small', 
          768, 
          chat_user => 'bob',
          api_key_name => 'MY_OPENAI_API_KEY_NAME'
        ),
        -- other parameters...
    );
    ```

#### Parameters

The function takes several parameters to customize the OpenAI embedding configuration:

| Name         | Type | Default          | Required | Description                                                                                                                                                                                                                                                                               |
|--------------|------|------------------|----------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| model        | text | -                | ✔        | Specify the name of the OpenAI embedding model to use. For example, `text-embedding-3-small`.                                                                                                                                                                                             |
| dimensions   | int  | -                | ✔        | Define the number of dimensions for the embedding vectors. This should match the output dimensions of the chosen model.                                                                                                                                                                   |
| chat_user    | text | -                | ✖        | The identifier for the user making the API call. This can be useful for tracking API usage or for OpenAI's monitoring purposes.                                                                                                                                                           |
| api_key_name | text | `OPENAI_API_KEY` | ✖        | Set [the name of the environment variable that contains the OpenAI API key][openai-use-env-var]. This allows for flexible API key management without hardcoding keys in the database. On Timescale Cloud, you should set this to the name of the secret that contains the OpenAI API key. |
#### Returns

A JSON configuration object that you can use in [ai.create_vectorizer](#create-vectorizers).

### ai.embedding_ollama

You use the `ai.embedding_ollama` function to use an Ollama model to generate embeddings.

The purpose of `ai.embedding_ollama` is to:
- Define which Ollama model to use.
- Specify the dimensionality of the embeddings.
- Configure how the Ollama API is accessed.
- Configure the model's truncation behaviour, and keep alive.
- Configure optional, model-specific parameters, like the `temperature`.

#### Example usage

This function is used to create an embedding configuration object that is passed as an argument to [ai.create_vectorizer](#create-vectorizers):

```sql
SELECT ai.create_vectorizer(
    'my_table'::regclass,
    embedding => ai.embedding_ollama(
      'nomic-embed-text',
      768,
      base_url => "http://my.ollama.server:443"
      options => '{ "num_ctx": 1024 }',
      keep_alive => "10m"
    ),
    -- other parameters...
);
```

#### Parameters

The function takes several parameters to customize the Ollama embedding configuration:

| Name       | Type    | Default | Required | Description                                                                                                                                                              |
|------------|---------|---------|----------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| model      | text    | -       | ✔        | Specify the name of the Ollama model to use. For example, `nomic-embed-text`. Note: the model must already be available (pulled) in your Ollama server.                  |
| dimensions | int     | -       | ✔        | Define the number of dimensions for the embedding vectors. This should match the output dimensions of the chosen model.                                                  |
| base_url   | text    | -       | ✖        | Set the base_url of the Ollama API. Note: no default configured here to allow configuration of the vectorizer worker through `OLLAMA_HOST` env var.                      |
| options    | jsonb   | -       | ✖        | Configures additional model parameters listed in the documentation for the Modelfile, such as `temperature`, or `num_ctx`.                                               |
| keep_alive | text    | -       | ✖        | Controls how long the model will stay loaded in memory following the request. Note: no default configured here to allow configuration at Ollama-level.                   |

#### Returns

A JSON configuration object that you can use in [ai.create_vectorizer](#create-vectorizers).

### ai.embedding_voyageai

You use the `ai.embedding_voyageai` function to use a Voyage AI model to generate embeddings.

The purpose of `ai.embedding_voyageai` is to:
- Define which Voyage AI model to use.
- Specify the dimensionality of the embeddings.
- Configure the model's truncation behaviour, and api key name.
- Configure the input type.

#### Example usage

This function is used to create an embedding configuration object that is passed as an argument to [ai.create_vectorizer](#create-vectorizers):

```sql
SELECT ai.create_vectorizer(
    'my_table'::regclass,
    embedding => ai.embedding_voyageai(
      'voyage-3-lite',
      512,
      api_key_name => "TEST_API_KEY"
    ),
    -- other parameters...
);
```

#### Parameters

The function takes several parameters to customize the Voyage AI embedding configuration:

| Name         | Type    | Default          | Required | Description                                                                                                                                                                                                                                                               |
|--------------|---------|------------------|----------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| model        | text    | -                | ✔        | Specify the name of the [Voyage AI model](https://docs.voyageai.com/docs/embeddings#model-choices) to use.                                                                                                                                                                |
| dimensions   | int     | -                | ✔        | Define the number of dimensions for the embedding vectors. This should match the output dimensions of the chosen model.                                                                                                                                                   |
| input_type   | text    | 'document'       | ✖        | Type of the input text, null, 'query', or 'document'.                                                                                                                                                                                                                     |
| api_key_name | text    | `VOYAGE_API_KEY` | ✖        | Set the name of the environment variable that contains the Voyage AI API key. This allows for flexible API key management without hardcoding keys in the database. On Timescale Cloud, you should set this to the name of the secret that contains the Voyage AI API key. |

#### Returns

A JSON configuration object that you can use in [ai.create_vectorizer](#create-vectorizers).

## Formatting configuration

You use the `ai.formatting_python_template` function in `pgai` to 
configure the way data from the source table is formatted before it is sent 
for embedding. 

`ai.formatting_python_template` provides a flexible way to structure the input
for embedding models. This enables you to incorporate relevant metadata and additional
text. This can significantly enhance the quality and usefulness of the generated
embeddings, especially in scenarios where context from multiple fields is
important for understanding or searching the content.

The purpose of `ai.formatting_python_template` is to:
- Define a template for formatting the data before embedding.
- Allow the combination of multiple fields from the source table.
- Add consistent context or structure to the text being embedded.
- Customize the input for the embedding model to improve relevance and searchability.

Formatting happens after chunking and the special `$chunk` variable contains the chunked text.

### Example usage

- Default formatting:

  The default formatter uses the `$chunk` template, resulting in outputing the chunk text as-is.
  
  ```sql
  SELECT ai.create_vectorizer(
      'blog_posts'::regclass,
      formatting => ai.formatting_python_template('$chunk'),
      -- other parameters...
  );
  ``` 
 
- Add context from other columns:

  Add the title and publication date to each chunk, providing more context for the embedding.
  ```sql
  SELECT ai.create_vectorizer(
      'blog_posts'::regclass,
      formatting => ai.formatting_python_template('Title: $title\nDate: $published\nContent: $chunk'),
      -- other parameters...
  );
  ```
  
- Combine multiple fields:

  Prepend author and category information to each chunk.
    ```sql
  SELECT ai.create_vectorizer(
      'blog_posts'::regclass,
      formatting => ai.formatting_python_template('Author: $author\nCategory: $category\n$chunk'),
      -- other parameters...
  );
  ```

- Add consistent structure:

  Add start and end markers to each chunk, which could be useful for certain
  types of embeddings or retrieval tasks.
  
  ```sql
  SELECT ai.create_vectorizer(
      'blog_posts'::regclass,
      formatting => ai.formatting_python_template('BEGIN DOCUMENT\n$chunk\nEND DOCUMENT'),
      -- other parameters...
  );
  ```

### Parameters

`ai.formatting_python_template` takes the following parameter:

|Name| Type   | Default | Required | Description                                                                                                                                                                       |
|-|--------|-|-|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|template| string |`$chunk`|✔| A string using [Python template strings](https://docs.python.org/3/library/string.html#template-strings) with $-prefixed variables that defines how the data should be formatted. |

  - The $chunk placeholder is required and represents the text chunk that will be embedded.
  - Other placeholders can be used to reference columns from the source table.
  - The template allows for adding static text or structuring the input in a specific way.

### Returns 

A JSON configuration object that you can use as an argument for [ai.create_vectorizer](#create-vectorizers).

## Indexing configuration

You use indexing configuration functions in pgai to 
specify the way generated embeddings should be indexed for efficient similarity 
searches. These functions enable you to choose and configure the indexing 
method that best suits your needs in terms of performance, accuracy, and 
resource usage. 

By providing these indexing options, pgai allows you to optimize your
embedding storage and retrieval based on their specific use case and performance
requirements. This flexibility is crucial for scaling AI-powered search and
analysis capabilities within a PostgreSQL database.

Key points about indexing:

- The choice of indexing method depends on your dataset size, query performance requirements, and available resources.

- [ai.indexing_none](#aiindexing_none) is better suited for small datasets, or when you want to perform index creation manually.
- [ai.indexing_diskann](#aiindexing_diskann) is generally recommended for larger datasets that require an index.

- The `min_rows` parameter enables you to delay index creation until you have enough data to justify the overhead.

- These indexing methods are designed for approximate nearest neighbor search, which trades a small amount of accuracy for significant speed improvements in similarity searches.

The available functions are:

- [ai.indexing_default](#aiindexing_default): when you do not want indexes created automatically.
- [ai.indexing_none](#aiindexing_none): when you do not want indexes created automatically.
- [ai.indexing_diskann](#aiindexing_diskann): configure indexing using the [DiskANN algorithm](https://github.com/timescale/pgvectorscale).
- [ai.indexing_hnsw](#aiindexing_hnsw): configure indexing using the [Hierarchical Navigable Small World (HNSW) algorithm](https://en.wikipedia.org/wiki/Hierarchical_navigable_small_world).

### ai.indexing_default

You use `ai.indexing_default` to use the platform-specific default value for indexing.

On Timescale Cloud, the default is `ai.indexing_diskann()`. On self-hosted, the default is `ai.indexing_none()`.
A timescaledb background job is used for automatic index creation. Since timescaledb may not be installed
in a self-hosted environment, we default to `ai.indexing_none()`.

#### Example usage

```sql
  SELECT ai.create_vectorizer(
      'blog_posts'::regclass,
      indexing => ai.indexing_default(),
      -- other parameters...
  );
```

#### Parameters

This function takes no parameters.

#### Returns

A JSON configuration object that you can use as an argument for [ai.create_vectorizer](#create-vectorizers).

### ai.indexing_none

You use `ai.indexing_none` to specify that no special indexing should be used for the embeddings.

This is useful when you don't need fast similarity searches or when you're dealing with a small amount of data.

#### Example usage

```sql
  SELECT ai.create_vectorizer(
      'blog_posts'::regclass,
      indexing => ai.indexing_none(),
      -- other parameters...
  );
```

#### Parameters

This function takes no parameters.

#### Returns

A JSON configuration object that you can use as an argument for [ai.create_vectorizer](#create-vectorizers).

### ai.indexing_diskann

You use `ai.indexing_diskann` to configure indexing using the DiskANN algorithm, which is designed for high-performance 
approximate nearest neighbor search on large-scale datasets. This is suitable for very large datasets that need to be 
stored on disk.

#### Example usage

```sql
  SELECT ai.create_vectorizer(
      'blog_posts'::regclass,
      indexing => ai.indexing_diskann(min_rows => 500000, storage_layout => 'memory_optimized'),
      -- other parameters...
  );
```

#### Parameters

`ai.indexing_diskann` takes the following parameters:

| Name | Type | Default | Required | Description                                      |
|------|------|---------|-|--------------------------------------------------|
|min_rows| int  | 100000  |✖| The minimum number of rows before creating the index |
|   storage_layout   | text | -       |✖| Set to either `memory_optimized` or `plain` |
|   num_neighbors   | int  | -       |✖|  Advanced  [DiskANN](https://github.com/microsoft/DiskANN/tree/main) parameter. |
|   search_list_size   |   int   | -       |✖| Advanced  [DiskANN](https://github.com/microsoft/DiskANN/tree/main) parameter.|
|   max_alpha   |  float8    | -       |✖| Advanced  [DiskANN](https://github.com/microsoft/DiskANN/tree/main) parameter.|
|  num_dimensions    |    int  | -       |✖|Advanced  [DiskANN](https://github.com/microsoft/DiskANN/tree/main) parameter.|
|   num_bits_per_dimension   |   int   | -       |✖| Advanced  [DiskANN](https://github.com/microsoft/DiskANN/tree/main) parameter.|
|   create_when_queue_empty   |   boolean   | true       |✖| Create the index only after all of the embeddings have been generated. |


#### Returns

A JSON configuration object that you can use as an argument for [ai.create_vectorizer](#create-vectorizers).

### ai.indexing_hnsw

You use `ai.indexing_hnsw` to configure indexing using the [Hierarchical Navigable Small World (HNSW) algorithm](https://en.wikipedia.org/wiki/Hierarchical_navigable_small_world), 
which is known for fast and accurate approximate nearest neighbor search.

HNSW is suitable for in-memory datasets and scenarios where query speed is crucial.

#### Example usage

```sql
  SELECT ai.create_vectorizer(
      'blog_posts'::regclass,
      indexing => ai.indexing_hnsw(min_rows => 50000, opclass => 'vector_l1_ops'),
      -- other parameters...
  );
```

#### Parameters

`ai.indexing_hnsw` takes the following parameters:

| Name | Type | Default             | Required | Description                                                                                                    |
|------|------|---------------------|-|----------------------------------------------------------------------------------------------------------------|
|min_rows| int  | 100000              |✖| The minimum number of rows before creating the index                                                           |
|opclass| text  | `vector_cosine_ops` |✖| The operator class for the index. Possible values are:`vector_cosine_ops`, `vector_l1_ops`, or `vector_ip_ops` |
|m| int  | -                   |✖| Advanced [HNSW parameters](https://en.wikipedia.org/wiki/Hierarchical_navigable_small_world)                   |
|ef_construction| int  | -                   |✖| Advanced [HNSW parameters](https://en.wikipedia.org/wiki/Hierarchical_navigable_small_world)                   |
| create_when_queue_empty| boolean | true |✖| Create the index only after all of the embeddings have been generated.                                         |


#### Returns

A JSON configuration object that you can use as an argument for [ai.create_vectorizer](#create-vectorizers).

## Scheduling configuration

You use scheduling functions in pgai to configure when and how often the vectorizer should run to process new or 
updated data. These functions allow you to set up automated, periodic execution of the embedding 
generation process. These are advanced options and most users should use the default.

By providing these scheduling options, pgai enables you to automate the process
of keeping your embeddings up-to-date with minimal manual intervention. This is
crucial for maintaining the relevance and accuracy of AI-powered search and
analysis capabilities, especially in systems where data is frequently updated or
added. The flexibility in scheduling also allows users to balance the freshness
of embeddings against system resource usage and other operational
considerations.

The available functions are:

- [ai.scheduling_default](#aischeduling_default): uses the platform-specific default scheduling configuration. On Timescale Cloud this is equivalent to `ai.scheduling_timescaledb()`. On self-hosted deployments, this is equivalent to `ai.scheduling_none()`.
- [ai.scheduling_none](#aischeduling_none): when you want manual control over when the vectorizer runs. Use this when you're using an external scheduling system, as is the case with self-hosted deployments.
- [ai.scheduling_timescaledb](#aischeduling_timescaledb): leverages TimescaleDB's robust job scheduling system, which is designed for reliability and scalability. Use this when you're using Timescale Cloud.


### ai.scheduling_default

You use `ai.scheduling_default` to use the platform-specific default scheduling configuration.

On Timescale Cloud, the default is `ai.scheduling_timescaledb()`. On self-hosted, the default is `ai.scheduling_none()`.
A timescaledb background job is used to periodically trigger a cloud vectorizer on Timescale Cloud.
This is not available in a self-hosted environment.

#### Example usage

```sql
SELECT ai.create_vectorizer(
    'my_table'::regclass,
    scheduling => ai.scheduling_default(),
    -- other parameters...
);
```

#### Parameters

This function takes no parameters.

#### Returns

A JSON configuration object that you can use as an argument for [ai.create_vectorizer](#create-vectorizers).

### ai.scheduling_none

You use `ai.scheduling_none` to
- Specify that no automatic scheduling should be set up for the vectorizer.
- Manually control when the vectorizer runs or when you're using an external scheduling system.

You should use this for self-hosted deployments.

#### Example usage

```sql
SELECT ai.create_vectorizer(
    'my_table'::regclass,
    scheduling => ai.scheduling_none(),
    -- other parameters...
);
```

#### Parameters

This function takes no parameters.

#### Returns

A JSON configuration object that you can use as an argument for [ai.create_vectorizer](#create-vectorizers).

### ai.scheduling_timescaledb

You use `ai.scheduling_timescaledb` to:

- Configure automated scheduling using TimescaleDB's job scheduling system.
- Allow periodic execution of the vectorizer to process new or updated data.
- Provide fine-grained control over when and how often the vectorizer runs.

#### Example usage

- Basic usage (run every 5 minutes). This is the default:

  ```sql
  SELECT ai.create_vectorizer(
      'my_table'::regclass,
      scheduling => ai.scheduling_timescaledb(),
      -- other parameters...
  );
  ```

- Custom interval (run every hour):
  ```sql
  SELECT ai.create_vectorizer(
      'my_table'::regclass,
      scheduling => ai.scheduling_timescaledb(interval '1 hour'),
      -- other parameters...
  );
  ```

- Specific start time and timezone:
  ```sql
  SELECT ai.create_vectorizer(
      'my_table'::regclass,
      scheduling => ai.scheduling_timescaledb(
        interval '30 minutes',
        initial_start => '2024-01-01 00:00:00'::timestamptz,
        timezone => 'America/New_York'
      ),
      -- other parameters...
  );
  ```

- Fixed schedule:
  ```sql
  SELECT ai.create_vectorizer(
      'my_table'::regclass,
      scheduling => ai.scheduling_timescaledb(
        interval '1 day',
        fixed_schedule => true,
        timezone => 'UTC'
      ),
      -- other parameters...
  );
  ```

#### Parameters

`ai.scheduling_timescaledb` takes the following parameters:

|Name|Type| Default | Required | Description                                                                                                        | 
|-|-|---------|-|--------------------------------------------------------------------------------------------------------------------|
|schedule_interval|interval| '10m'   |✔| Set how frequently the vectorizer checks for new or updated data to process.                                       |
|initial_start|timestamptz| -       |✖| Delay the start of scheduling. This is useful for coordinating with other system processes or maintenance windows. |
|fixed_schedule|bool| -       |✖|Set to `true` to use a fixed schedule such as every day at midnight. Set to `false` for a sliding window such as every 24 hours from the last run|
|timezone|text| - |✖|  Set the timezone this schedule operates in. This ensures that schedules are interpreted correctly, especially important for fixed schedules or when coordinating with business hours. |

#### Returns

A JSON configuration object that you can use as an argument for [ai.create_vectorizer](#create-vectorizers).

## Processing configuration

You use the processing configuration functions in pgai to specify 
the way the vectorizer should process data when generating embeddings,
such as the batch size and concurrency. These are advanced options and most 
users should use the default.

### ai.processing_default

You use `ai.processing_default` to specify the concurrency and batch size for the vectorizer.

#### Example usage

```sql
  SELECT ai.create_vectorizer(
    'my_table'::regclass,
    processing => ai.processing_default(batch_size => 200, concurrency => 5),
    -- other parameters...
  );
```

#### Parameters

`ai.processing_default` takes the following parameters:

|Name| Type | Default                      | Required | Description                                                                                                                                                                                                           |
|-|------|------------------------------|-|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|batch_size| int  | Determined by the vectorizer |✖| The number of items to process in each batch. The optimal batch size depends on your data and cloud function configuration, larger batch sizes can improve efficiency but may increase memory usage.                  |
|concurrency| int  | Determined by the vectorizer |✖| The number of concurrent processing tasks to run. The optimal concurrency depends on your cloud infrastructure and rate limits, higher concurrency can speed up processing but may increase costs and resource usage. |

#### Returns

A JSON configuration object that you can use as an argument for [ai.create_vectorizer](#create-vectorizers).

## Grant To configuration

You use the grant to configuration function in pgai to specify which users should be able to use
objects created by the vectorizer.

### ai.grant_to

Grant permissions to a comma-separated list of users.

Includes the users specified in the `ai.grant_to_default` setting.

#### Example usage

```sql
  SELECT ai.create_vectorizer(
    'my_table'::regclass,
    grant_to => ai.grant_to('bob', 'alice'),
    -- other parameters...
  );
```

#### Parameters

This function takes a comma-separated list of usernames to grant permissions to.

#### Returns

An array of name values, that you can use as an argument for [ai.create_vectorizer](#create-vectorizers).

## Enable and disable vectorizer schedules

You use `ai.enable_vectorizer_schedule` and `ai.disable_vectorizer_schedule` to control
the execution of [scheduled vectorizer jobs](#scheduling-configuration). These functions 
provide a way to temporarily pause or resume the automatic processing of embeddings, without 
having to delete or recreate the vectorizer configuration. 

These functions provide an important layer of operational control for managing
pgai vectorizers in production environments. They allow database administrators
and application developers to balance the need for up-to-date embeddings with
other system priorities and constraints, enhancing the overall flexibility and
manageability of pgai.

Key points about schedule enable and disable:

- These functions provide fine-grained control over individual vectorizer schedules without affecting other 
  vectorizers, or the overall system configuration.

- Disabling a schedule does not delete the vectorizer or its configuration; it simply stops scheduling future
  executions of the job.

- These functions are particularly useful in scenarios such as:
  - System maintenance windows where you want to reduce database load.
  - Temporarily pausing processing during data migrations or large bulk updates.
  - Debugging or troubleshooting issues related to the vectorizer.
  - Implementing manual control over when embeddings are updated.

- When a schedule is disabled, new or updated data is not automatically processed. However, the data is still 
   queued, and will be processed when the schedule is re-enabled, or when the vectorizer is run manually.

- These functions only affect vectorizers configured with [ai.scheduling_timescaledb](#aischeduling_timescaledb). 
  Vectorizers configured with [ai.scheduling_none](#aischeduling_none) are not affected.

- After re-enabling a schedule, the next run is based on the original scheduling configuration. For example, 
  if the vectorizer was set to run every hour, it will run at the next hour mark after being enabled.

Usage example in a maintenance scenario:

```sql
-- Before starting system maintenance
SELECT ai.disable_vectorizer_schedule(1);
SELECT ai.disable_vectorizer_schedule(2);

-- Perform maintenance tasks...

-- After maintenance is complete
SELECT ai.enable_vectorizer_schedule(1);
SELECT ai.enable_vectorizer_schedule(2);
```

The available functions are:
- [ai.enable_vectorizer_schedule](#aienable_vectorizer_schedule): activate, reactivate or resume a scheduled job.
- [ai.disable_vectorizer_schedule](#aidisable_vectorizer_schedule): disactivate or temporarily stop a scheduled job.

### ai.enable_vectorizer_schedule

You use `ai.enable_vectorizer_schedule` to:
- Activate or reactivate the scheduled job for a specific vectorizer.
- Allow the vectorizer to resume automatic processing of new or updated data.

#### Example usage

To resume the automatic scheduling for the vectorizer with ID 1.

```sql
SELECT ai.enable_vectorizer_schedule(1);
```

#### Parameters

`ai.enable_vectorizer_schedule` takes the following parameters:

|Name| Type | Default | Required | Description                                               |
|-|------|---------|-|-----------------------------------------------------------|
|vectorizer_id| int  | -       |✔| The identifier of the vectorizer whose schedule you want to enable. |

#### Returns

`ai.enable_vectorizer_schedule` does not return a value,

### ai.disable_vectorizer_schedule

You use `ai.disable_vectorizer_schedule` to:
- Deactivate the scheduled job for a specific vectorizer.
- Temporarily stop the automatic processing of new or updated data.


#### Example usage

To stop the automatic scheduling for the vectorizer with ID 1.

```sql
SELECT ai.disable_vectorizer_schedule(1);
```

#### Parameters

`ai.disable_vectorizer_schedule` takes the following parameters:

|Name| Type | Default | Required | Description                                                          |
|-|------|---------|-|----------------------------------------------------------------------|
|vectorizer_id| int  | -       |✔| The identifier of the vectorizer whose schedule you want to disable. |

#### Returns

`ai.disable_vectorizer_schedule` does not return a value,


## Drop a vectorizer

`ai.drop_vectorizer` is a management tool that you use to remove a vectorizer that you  
[created previously](#create-vectorizers), and clean up the associated 
resources. Its primary purpose is to provide a controlled way to delete a 
vectorizer when it's no longer needed, or when you want to reconfigure it from 
scratch.

You use `ai.drop_vectorizer` to:
- Remove a specific vectorizer configuration from the system.
- Clean up associated database objects and scheduled jobs.
- Safely undo the creation of a vectorizer.

`ai.drop_vectorizer` performs the following on the vectorizer to drop:

- Deletes the scheduled job associated with the vectorizer if one exists.
- Drops the trigger from the source table used to queue changes.
- Drops the trigger function that backed the source table trigger.
- Drops the queue table used to manage the updates to be processed.
- Deletes the vectorizer row from the `ai.vectorizer` table.

By default, `ai.drop_vectorizer` does not:

- Drop the target table containing the embeddings.
- Drop the view joining the target and source tables.

There is an optional parameter named `drop_all` which is `false` by default. If you
explicitly pass `true`, the function WILL drop the target table and view.

This design allows you to keep the generated embeddings and the convenient view
even after dropping the vectorizer. This is useful if you want to stop
automatic updates but still use the existing embeddings.

#### Example usage

Best practices are:

- Before dropping a vectorizer, ensure that you will not need the automatic embedding updates it provides.
- After dropping a vectorizer, you may want to manually clean up the target table and view if they're no longer needed.
- To ensure that you are dropping the correct vectorizer, keep track of your vectorizer IDs. You can do this by querying 
  the `ai.vectorizer` table.


Examples: 
- Remove the vectorizer with ID 1:

  ```sql
  -- Assuming we have a vectorizer with ID 1
  SELECT ai.drop_vectorizer(1);
  ```

- Remove the vectorizer with ID 1 and drop the target table and view as well:

  ```sql
  SELECT ai.drop_vectorizer(1, drop_all=>true);
  ```

#### Parameters

`ai.drop_vectorizer` takes the following parameters:

|Name| Type | Default | Required | Description |
|-|------|-|-|-|
|vectorizer_id| int  | -|✔|The identifier of the vectorizer you want to drop|
|drop_all| bool | false |✖|true to drop the target table and view as well|

#### Returns

`ai.drop_vectorizer` does not return a value, but it performs several cleanup operations.

## View vectorizer status

[ai.vectorizer_status view](#aivectorizer_status-view) and 
[ai.vectorizer_queue_pending function](#aivectorizer_queue_pending-function) are 
monitoring tools in pgai that provide insights into the state and performance of vectorizers. 

These monitoring tools are crucial for maintaining the health and performance of
your pgai-enhanced database. They allow you to proactively manage your
vectorizers, ensure timely processing of embeddings, and quickly identify and
address any issues that may arise in your AI-powered data pipelines.

For effective monitoring, you use `ai.vectorizer_status`.

For example:
```sql
-- Get an overview of all vectorizers
SELECT * FROM ai.vectorizer_status;
```

Sample output:

| id | source_table | target_table | view | pending_items |
|----|--------------|--------------|------|---------------|
| 1 | public.blog | public.blog_contents_embedding_store | public.blog_contents_embeddings | 1 |

The `pending_items` column indicates the number of items still awaiting embedding creation. The pending items count helps you to:
- Identify bottlenecks in processing.
- Determine if you need to adjust scheduling or processing configurations.
- Monitor the impact of large data imports or updates on your vectorizers.

Regular monitoring using these tools helps ensure that your vectorizers are keeping up with data changes, and that 
embeddings remain up-to-date.


Available views are:
- [ai.vectorizer_status](#aivectorizer_status-view): view, monitor and display information about a vectorizer. 

Available functions are:
- [ai.vectorizer_queue_pending](#aivectorizer_queue_pending-function): retrieve just the queue count for a vectorizer.


### ai.vectorizer_status view

You use `ai.vectorizer_status` to:
- Get a high-level overview of all vectorizers in the system.
- Regularly monitor and check the health of the entire system.
- Display key information about each vectorizer's configuration and current state.
- Use the `pending_items` column to get a quick indication of processing backlogs.

#### Example usage

- Retrieve all vectorizers that have items waiting to be processed:

  ```sql
  SELECT * FROM ai.vectorizer_status WHERE pending_items > 0;
  ```

- System health monitoring:
   ```sql
   -- Alert if any vectorizer has more than 1000 pending items
   SELECT id, source_table, pending_items 
   FROM ai.vectorizer_status 
   WHERE pending_items > 1000;
   ```

#### Returns

`ai.vectorizer_status` returns the following:

| Column name   | Description                                                           |
|---------------|-----------------------------------------------------------------------|
| id | The unique identifier of this vectorizer                              |
|source_table  | The fully qualified name of the source table                          |
|target_table  | The fully qualified name of the table storing the embeddings          |
|view  | The fully qualified name of the view joining source and target tables |
| pending_items | The number of items waiting to be processed by the vectorizer         |

### ai.vectorizer_queue_pending function

`ai.vectorizer_queue_pending` enables you to retrieve the number of items in a vectorizer queue 
when you need to focus on a particular vectorizer or troubleshoot issues.

You use `vectorizer_queue_pending` to:
- Retrieve the number of pending items for a specific vectorizer.
- Allow for more granular monitoring of individual vectorizer queues.

#### Example usage

Return the number of pending items for the vectorizer with ID 1:

  ```sql
  SELECT ai.vectorizer_queue_pending(1);
  ```

A queue with a very large number of items may be slow to count. The optional 
`exact_count` parameter is defaulted to false. When false, the count is limited.
An exact count is returned if the queue has 10,000 or fewer items, and returns
9223372036854775807 (the max bigint value) if there are greater than 10,000 
items.

To get an exact count, regardless of queue size, set the optional parameter to
`true` like this:

  ```sql
  SELECT ai.vectorizer_queue_pending(1, exact_count=>true);
  ```

#### Parameters

`ai.vectorizer_queue_pending function` takes the following parameters:

| Name          | Type | Default | Required | Description                                             |
|---------------|------|---------|----------|---------------------------------------------------------|
| vectorizer_id | int  | -       | ✔        | The identifier of the vectorizer you want to check      |
| exact_count   | bool | false   | ✖        | If true, return exact count. If false, capped at 10,000 |


### Returns

The number of items in the queue for the specified vectorizer

[timescale-cloud]: https://console.cloud.timescale.com/
[openai-use-env-var]: https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety#h_a1ab3ba7b2
[openai-set-key]: https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety#h_a1ab3ba7b2
[docker configuration]: https://github.com/timescale/pgai/blob/main/docs/vectorizer-worker.md#install-and-configure-vectorizer-worker
