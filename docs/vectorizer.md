
# Vectorizers

A vectorizer provides you with a powerful and automated way to generate and 
manage LLM embeddings for your PostgreSQL data. Here's a summary of what you 
gain from Vectorizers:

- **Automated embedding generation**: you can create a vectorizer for a specified
   table, which automatically generates embeddings for the data in that table.

- **Configurable embedding process**: a vectorizer is highly configurable, 
   allowing you to specify:
    - The embedding model and dimensions. For example, OpenAI's `text-embedding-3-small`.
    - Chunking strategies for text data.
    - Formatting templates for combining multiple fields.
    - Indexing options for efficient similarity searches.
    - Scheduling for background processing.

- **Integration with multiple AI providers**: a vectorizer supports different 
   embedding providers, initially including OpenAI, with more planned for the 
   future.

- **Automatic updates**: a vectorizer creates triggers on the source table, 
   ensuring that embeddings are automatically updated when the source data 
   changes.

- **Efficient storage and retrieval**: embeddings are stored in a separate table 
   with appropriate indexing, optimizing for vector similarity searches.

- **Background processing**: you can schedule a vectorizer to run as a background
   job, minimizing impact on regular database operations.

- **View creation**: a view is automatically created to join the original data with
   its embeddings, making it easy to query and use the embedded data.

- **Scalability**: a vectorizer includes options for batch processing and 
   concurrency control. This enables vectorizers to handle large datasets efficiently.

- **Fine-grained access control**: you can specify the roles that have 
    access to a vectorizer and its related objects.

- **Monitoring and management**:  monitor the vectorizer's queue, enable/disable scheduling, and manage the vectorizer 
    lifecycle.

Vectorizer significantly simplifies the process of incorporating AI-powered 
semantic search and analysis capabilities into existing PostgreSQL databases.  
Making it easier for you to leverage the power of LLMs in your data workflows.

Initially, vectorizers only work on [Timescale Cloud][timescale-cloud]. However 
support for self-hosted installations will be added quickly.

Vectorizer offers the following APIs:

- [Create vectorizers](#create-vectorizers): automate the process of creating embeddings for table data.
- [Chunking configuration](#chunking-configuration): define the way text data is split into smaller, manageable pieces 
  before being processed for embeddings.
- [Embedding configuration](#embedding-configuration): create a standardized configuration object that can be used by 
  other pgai functions.
- [Formatting configuration](#formatting-configuration): configure the way data from the source table is formatted
  before it is sent for embedding.
- [Indexing configuration](#indexing-configuration): specify the way generated embeddings should be indexed for 
  efficient similarity searches.
- [Scheduling configuration](#scheduling-configuration): configure when and how often the vectorizer should run in order 
  to process new or updated data.
- [Enable and disable vectorizer schedules](#enable-and-disable-vectorizer-schedules): temporarily pause or resume the 
  automatic processing of embeddings, without having to delete or recreate the vectorizer configuration.
- [Processing configuration](#processing-configuration): specify the way the vectorizer should process data when 
  generating embeddings.
- [Drop a vectorizer](#drop-a-vectorizer): remove a vectorizer that you created previously, and clean up the associated
  resources.
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
    embedding => ai.embedding_openai('text-embedding-3-small', 768),
    chunking => ai.chunking_character_text_splitter('body', 128, 10),
    formatting => ai.formatting_python_template('title: $title published: $published $chunk'),
    scheduling => ai.scheduling_timescaledb(
        interval '5m',
        initial_start => '2050-01-06'::timestamptz,
        timezone => 'America/Chicago'
    ),
    grant_to => array['bob', 'alice']
);
```

This function call:
1. Sets up a vectorizer for the `website.blog` table.
2. Uses OpenAI's `text-embedding-3-small` model to create 768 dimensional embeddings.
3. Chunks the `body` column into 128-character pieces with a 10-character overlap.
4. Formats each chunk with a `title` and a `published` date.
5. Schedules the vectorizer to run every `5` minutes starting from a date in the future.
6. Grants necessary permissions to the roles `bob` and `alice`.

The function returns an integer identifier for the vectorizer created, which you can use
in other management functions.

### Parameters

`ai.create_vectorizer` takes the following parameters:

| Name             | Type                                                   | Default                           | Required | Description                                                                                        |
|------------------|--------------------------------------------------------|-----------------------------------|-|----------------------------------------------------------------------------------------------------|
| source           | regclass                                               | -                                 |✔| The source table that embeddings are generated for.                                                |
| destination      | name                                                   | -                                 | ✖| A name for the table the embeddings are stored in.                                                 |
| embedding        | [Embedding configuration](#embedding-configuration)    | -                                 |✖| Set the embedding process using `ai.embedding_openai()` to specify the model and dimensions.       |
| chunking         | [Chunking configuration](#chunking-configuration)      | -                                 |✖| Set the way to split text data, using functions like `ai.chunking_character_text_splitter()`.      |
| indexing         | [Indexing configuration](#indexing-configuration)      | `ai.indexing_diskann()`           |✖| Specify how to index the embeddings. For example, `ai.indexing_diskann()` or `ai.indexing_hnsw()`. |
| formatting       | [Formatting configuration](#formatting-configuration)  | `ai.formatting_python_template()` | ✖| Define the data format before embedding, using `ai.formatting_python_template()`.                  |
| scheduling       | [Scheduling configuration](#scheduling-configuration)  | `ai.scheduling_timescaledb()`     |✖| Set how often to run the vectorizer. For example, `ai.scheduling_timescaledb()`.                   |
| processing       | [Processing configuration](#processing-configuration ) | `ai.processing_default()`         |✖| Configure the way to process the embeddings.                                                       |
| target_schema    | name                                                   | -                                 |✖| Specify where to store embeddings and create views.                                                |
| target_table     | name                                                   | -                                 |✖| Specify where to store embeddings and create views.                                                |
| view_schema      | name                                                   | -                                 |✖| Specify where to store embeddings and create views.                                                |
| view_name        | name                                                   | -                                 |✖| Specify where to store embeddings and create views.                                                |
| queue_schema     | name                                                   | -                                 |✖| Set the way the queue works in background processing.                                              |
| queue_table      |  name                                                      | -                                 |✖| Set the way the queue works in background processing.                                              |
| grant_to         | name[]                                                  | `array['tsdbadmin']`              |✖ | An array containing the role names to grant permissions to.                                        |
| enqueue_existing | bool                                                   | `true`                             |✖| Set to `true` if existing rows should be immediately queued for embedding.   |


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

To split the `body` column into chunks of 128 characters, with 10
character overlap, using '\n;' as the separator:

```sql
SELECT ai.chunking_character_text_splitter('body', 128, 10, E'\n;')
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

- Split the `my_table` table into chunks of 128 characters, with a 10 character overlap:

  ```sql
  SELECT ai.create_vectorizer(
      'my_table'::regclass,
      chunking => ai.chunking_character_text_splitter('body', 128, 10),
      -- other parameters...
  );
  ```

- Recursively split the `content` column into chunks of 256 characters, with a 20 character 
  overlap, first trying to split on '\n;', then on spaces:

  ```sql
  SELECT ai.chunking_recursive_character_text_splitter(
      'content', 
      256, 
      20, 
      separators => array[E'\n;', ' ']
  )
  ```

#### Parameters

`ai.chunking_recursive_character_text_splitter` takes the following parameters:

|Name| Type | Default | Required | Description                                              |
|-|------|---------|-|----------------------------------------------------------|
|chunk_column| name | -       |✔| The name of the column containing the text to be chunked |
|chunk_size| int  | 800     |✖| The maximum number of characters per chunk               |
|chunk_overlap| int  | 400     |✖| The number of characters to overlap between chunks       |
|separator| text[] | array[E'\n\n', E'\n', '.', '?', '!', ' ', ''] |✖| The string or character used to split the text |
|is_separator_regex| bool | false   |✖| Set to `true` if    `separator` is a regular expression. |

#### Returns

A JSON configuration object that you can use in [ai.create_vectorizer](#create-vectorizers).

## Embedding configuration

You use the `ai.embedding_openai` configuration function in pgai to create a standardized configuration 
object that can be used by other pgai functions, particularly [ai.create_vectorizer](#create-vectorizers), 
to set up embedding generation using OpenAI's API.

`ai.embedding_openai` also provides a layer of abstraction, allowing pgai
to handle the details of interacting with the OpenAI API based on this
configuration, simplifying the process for users who may not be familiar with
the specifics of the OpenAI API.

The purpose of `ai.embedding_openai` is to:
- Define which OpenAI embedding model to use.
- Specify the dimensionality of the embeddings.
- Configure optional parameters like the user identifier for API calls.
- Set the name of the environment variable that contains the OpenAI API key.

This makes it easier to switch between different embedding providers or models in the future by using a different,
configuration function.

### Example usage

```sql
SELECT ai.embedding_openai(
    'text-embedding-3-small', 
    768, 
    chat_user => 'bob',
    api_key_name => 'MY_OPENAI_API_KEY'
);
```

This function call returns a JSON configuration object that looks something like this:

```json
{
    "implementation": "openai",
    "config_type": "embedding",
    "model": "text-embedding-3-small",
    "dimensions": 768,
    "user": "bob",
    "api_key_name": "MY_OPENAI_API_KEY"
}
```

You use this configuration object as an argument for [ai.create_vectorizer](#create-vectorizers):

```sql
SELECT ai.create_vectorizer(
    'my_table'::regclass,
    embedding => ai.embedding_openai('text-embedding-3-small', 768),
    -- other parameters...
);
```

### Parameters

The function takes several parameters to customize the OpenAI embedding configuration:

|Name| Type | Default | Required | Description                                                                                                                                                    |
|-|------|-|-|----------------------------------------------------------------------------------------------------------------------------------------------------------------|
|model| text | -|✔| Specify the name of the OpenAI embedding model to use. For example, `text-embedding-3-small`.                                                                   |
|dimensions| int  | -|✔| Define the number of dimensions for the embedding vectors. This should match the output dimensions of the chosen model.                                        |
|chat_user| text | -|✖| The identifier for the user making the API call. This can be useful for tracking API usage or for OpenAI's monitoring purposes.                                |
|api_key_name|  text    | `OPENAI_API_KEY`|✖| Set the name of the environment variable that contains the OpenAI API key. This allows for flexible API key management without hardcoding keys in the database. |

#### Returns

A JSON configuration object that you can use in [ai.create_vectorizer](#create-vectorizers).

## Formatting configuration

You use the `ai.formatting_python_template` function in `pgai` to 
configure the way data from the source table is formatted before it is sent 
for embedding. 

`ai.formatting_python_template` provides a flexible way to
structure the input for embedding models. This enables you to incorporate relevant
metadata or add consistent formatting to their text data. This can significantly
enhance the quality and usefulness of the generated embeddings, especially in
scenarios where context from multiple fields is important for understanding or
searching the content.

The purpose of `ai.formatting_python_template` is to:
- Define a template for formatting the data before embedding.
- Allow the combination of multiple fields from the source table.
- Add consistent context or structure to the text being embedded.
- Customize the input for the embedding model to improve relevance and searchability.

This functionality can significantly enhance the quality and usefulness of the resulting 
embeddings.

### Example usage

- Basic usage (default):
  ```sql
  SELECT ai.formatting_python_template()
  ```
  The default `$chunk` template uses the chunked text as-is.

- Add context from other columns:

  Add the title and publication date to each chunk, providing more context for the embedding.
  ```sql
  SELECT ai.formatting_python_template('Title: $title\nDate: $published\nContent: $chunk')
  ```

- Combine multiple fields:

  Prepend author and category information to each chunk.
  ```sql
  SELECT ai.formatting_python_template('Author: $author\nCategory: $category\n$chunk')
  ```

- Add consistent structure:

  Add start and end markers to each chunk, which could be useful for certain
  types of embeddings or retrieval tasks.
  ```sql
  SELECT ai.formatting_python_template('BEGIN DOCUMENT\n$chunk\nEND DOCUMENT')
  ```

- Example usage within `ai.create_vectorizer`:

  Format each chunk of the `content` column with the
  title, author, and publication date before being sent for embedding. This can
  make the embeddings more informative and improve the accuracy of similarity
  searches or other downstream tasks.

  ```sql
  SELECT ai.create_vectorizer(
      'blog_posts'::regclass,
      embedding => ai.embedding_openai('text-embedding-3-small', 768),
      chunking => ai.chunking_character_text_splitter('content', 1000, 100),
      formatting => ai.formatting_python_template('Title: $title\nAuthor: $author\nDate: $published\nContent: $chunk'),
      -- other parameters...
  );
  ```

### Parameters

`ai.formatting_python_template` takes the following parameter:

|Name| Type   | Default | Required | Description                                                                                                                 |
|-|--------|-|-|-----------------------------------------------------------------------------------------------------------------------------|
|template| string |`$chunk`|✔| A string using [Python string formatting](https://realpython.com/python-string-formatting/) with $-prefixed variables that defines how the data should be formatted. |

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

- [ai.indexing_none](#aiindexing_none) is better suited for small datasets, or when you're more concerned with insertion speed than query speed.

- [ai.indexing_diskann](#aiindexing_diskann) is generally better for very large datasets that don't fit in memory.
- [ai.indexing_hnsw](#aiindexing_hnsw) is often faster for in-memory datasets.

- The `min_rows` parameter enables you to delay index creation until you have enough data to justify the overhead.

- These indexing methods are designed for approximate nearest neighbor search, which trades a small amount of accuracy for significant speed improvements in similarity searches.

The available functions are:

- [ai.indexing_none](#aiindexing_none): configure indexing using the [Hierarchical Navigable Small World (HNSW) algorithm](https://en.wikipedia.org/wiki/Hierarchical_navigable_small_world).
- [ai.indexing_diskann](#aiindexing_diskann): configure indexing using the DiskANN algorithm.
- [ai.indexing_hnsw](#aiindexing_hnsw): configure indexing using the [Hierarchical Navigable Small World (HNSW) algorithm](https://en.wikipedia.org/wiki/Hierarchical_navigable_small_world).

### ai.indexing_none

You use `ai.indexing_none` to specify that no special indexing should be used for the embeddings.

This is useful when you don't need fast similarity searches or when you're dealing with a small amount of data.

#### Example usage

```sql
SELECT ai.indexing_none()
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
SELECT ai.indexing_diskann(min_rows => 500000, storage_layout => 'memory_optimized')
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


#### Returns

A JSON configuration object that you can use as an argument for [ai.create_vectorizer](#create-vectorizers).

### ai.indexing_hnsw

You use `ai.indexing_hnsw` to configure indexing using the [Hierarchical Navigable Small World (HNSW) algorithm](https://en.wikipedia.org/wiki/Hierarchical_navigable_small_world), 
which is known for fast and accurate approximate nearest neighbor search.

HNSW is suitable for in-memory datasets and scenarios where query speed is crucial.

#### Example usage

```sql
SELECT ai.indexing_hnsw(min_rows => 50000, opclass => 'vector_l2_ops')
```

You typically use indexing configuration functions as arguments to the
  `ai.create_vectorizer` function:

  ```sql
  SELECT ai.create_vectorizer(
      'my_embeddings'::regclass,
      embedding => ai.embedding_openai('text-embedding-3-small', 768),
      chunking => ai.chunking_character_text_splitter('text_column'),
      indexing => ai.indexing_hnsw(min_rows => 10000),
      -- other parameters...
  );
  ```

#### Parameters

`ai.indexing_hnsw` takes the following parameters:

| Name | Type | Default             | Required | Description                                                                                                    |
|------|------|---------------------|-|----------------------------------------------------------------------------------------------------------------|
|min_rows| int  | 100000              |✖| The minimum number of rows before creating the index                                                           |
|opclass| text  | `vector_cosine_ops` |✖| The operator class for the index. Possible values are:`vector_cosine_ops`, `vector_l2_ops`, or `vector_ip_ops` |
|m| int  | -                   |✖| Advanced [HNSW parameters](https://en.wikipedia.org/wiki/Hierarchical_navigable_small_world)                   |
|ef_construction| int  | -                   |✖|  Advanced [HNSW parameters](https://en.wikipedia.org/wiki/Hierarchical_navigable_small_world)                                                                                                              |


#### Returns

A JSON configuration object that you can use as an argument for [ai.create_vectorizer](#create-vectorizers).

## Scheduling configuration

You use scheduling functions in pgai to configure when and how often the vectorizer should run to process new or 
updated data. These functions allow you to set up automated, periodic execution of the embedding 
generation process.

By providing these scheduling options, pgai enables you to automate the process
of keeping your embeddings up-to-date with minimal manual intervention. This is
crucial for maintaining the relevance and accuracy of AI-powered search and
analysis capabilities, especially in systems where data is frequently updated or
added. The flexibility in scheduling also allows users to balance the freshness
of embeddings against system resource usage and other operational
considerations.

The available functions are:

- [ai.scheduling_none](#aischeduling_none): when you want manual control over when the vectorizer runs.
- [ai.scheduling_timescaledb](#aischeduling_timescaledb): leverages TimescaleDB's robust job scheduling system, which is designed for reliability and scalability.


### ai.scheduling_none

You use `ai.scheduling_none` to
- Specify that no automatic scheduling should be set up for the vectorizer.
- Manually control when the vectorizer runs or when you're using an external scheduling system.

#### Example usage

```sql
SELECT ai.scheduling_none()
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

- Basic usage (run every 10 minutes):
  ```sql
  SELECT ai.scheduling_timescaledb()
  ```

- Custom interval (run every hour):
  ```sql
  SELECT ai.scheduling_timescaledb(interval '1 hour')
  ```

- Specific start time and timezone:
  ```sql
  SELECT ai.scheduling_timescaledb(
      interval '30 minutes',
      initial_start => '2023-12-01 00:00:00'::timestamptz,
      timezone => 'America/New_York'
  )
  ```

- Fixed schedule:
  ```sql
  SELECT ai.scheduling_timescaledb(
      interval '1 day',
      fixed_schedule => true,
      timezone => 'UTC'
  )
  ```

- Usage in `ai.create_vectorizer`:

  These scheduling configuration functions are used as arguments to the
  `ai.create_vectorizer` function:
  
  ```sql
  SELECT ai.create_vectorizer(
      'my_table'::regclass,
      embedding => ai.embedding_openai('text-embedding-3-small', 768),
      chunking => ai.chunking_character_text_splitter('text_column'),
      scheduling => ai.scheduling_timescaledb(interval '15 minutes'),
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
SELECT ai.enable_vectorizer_schedule(1);
```

#### Parameters

`ai.enable_vectorizer_schedule` takes the following parameters:

|Name| Type | Default | Required | Description                                                          |
|-|------|---------|-|----------------------------------------------------------------------|
|vectorizer_id| int  | -       |✔| The identifier of the vectorizer whose schedule you want to disable. |

#### Returns

`ai.disable_vectorizer_schedule` does not return a value,

## Processing configuration

You use the processing configuration functions in pgai to specify 
the way the vectorizer should process data when generating embeddings. These 
functions allow you to choose between different processing strategies, 
balancing factors like performance, scalability, and infrastructure 
requirements. 

By providing these processing options, pgai enables you to choose the most appropriate strategy
for your specific use case, infrastructure, and performance requirements.

The available functions are:

- [ai.processing_none](#aiprocessing_none):
  - Offers simplicity, and keeps everything within the database.
  - Uses the default in-database processing.
  - Suitable for smaller datasets or when you want to keep all processing within the database.
  - Simpler setup as it doesn't require additional infrastructure.

- [ai.processing_cloud_functions](#aiprocessing_cloud_functions):
  - Scale out the embedding generation process for larger datasets or higher throughput requirements.
  - Enable distributed processing using cloud functions.
  - Can improve performance and scalability, especially for large datasets.
  - Reduce load on the database server by offloading embedding generation.
  - Requires additional setup and infrastructure for cloud functions.
  - Allows for fine-tuning of batch size and concurrency to optimize performance.


### ai.processing_none

You use `ai.processing_none` to:
- Indicate that no special processing configuration is needed.
- Use the default in-database processing for generating embeddings.

#### Example usage

To use the default processing:

```sql
SELECT ai.processing_none()
```

#### Parameters

This function takes no parameters.

#### Returns

A JSON configuration object that you can use as an argument for [ai.create_vectorizer](#create-vectorizers).

### ai.processing_cloud_functions

You use `ai.processing_cloud_functions` to:
- Configure the vectorizer to use cloud functions to proces embeddings.
- Enable distributed and scalable processing of embeddings outside the database.
- Allow for potential performance improvements and reduced load on the database server.

When using `ai.processing_cloud_functions`, you need to ensure that:
- Your cloud functions are properly set up and configured.
- The database can communicate with the cloud function service.
- You have considered security implications of sending data to cloud functions.

#### Example usage

- Basic usage (use system defaults):
  ```sql
  SELECT ai.processing_cloud_functions()
  ```

- Specify batch size:
  ```sql
  SELECT ai.processing_cloud_functions(batch_size => 100)
  ```

- Specifying batch size and concurrency:
  ```sql
  SELECT ai.processing_cloud_functions(batch_size => 50, concurrency => 5)
  ```

- Usage in `ai.create_vectorizer`:

  These processing configuration functions are used as arguments to the
  `ai.create_vectorizer` function:
  
  ```sql
  SELECT ai.create_vectorizer(
      'my_table'::regclass,
      embedding => ai.embedding_openai('text-embedding-3-small', 768),
      chunking => ai.chunking_character_text_splitter('text_column'),
      processing => ai.processing_cloud_functions(batch_size => 200),
      -- other parameters...
  );
  ```

#### Parameters

`ai.enable_vectorizer_schedule` takes the following parameters:

|Name| Type | Default                      | Required | Description                                                                                                                                                                                                           |
|-|------|------------------------------|-|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|batch_size| int  | Determined by the vectorizer |✖| The number of items to process in each batch. The optimal batch size depends on your data and cloud function configuration, larger batch sizes can improve efficiency but may increase memory usage.                  |
|concurrency| int  | Determined by the vectorizer |✖| The number of concurrent processing tasks to run. The optimal concurrency depends on your cloud infrastructure and rate limits, higher concurrency can speed up processing but may increase costs and resource usage. |

#### Returns

A JSON configuration object that you can use as an argument for [ai.create_vectorizer](#create-vectorizers).

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

`ai.drop_vectorizer` does not:

- Drop the target table containing the embeddings.
- Drop the view joining the target and source tables.

This design allows you to keep the generated embeddings and the convenient view
even after dropping the vectorizer. This is useful if you want to stop
automatic updates but still use the existing embeddings.


#### Example usage

Best practices are:

- Before dropping a vectorizer, ensure that you will not need the automatic embedding updates it provides.
- If you want to preserve the embeddings, make sure to backup or rename the target table before dropping the vectorizer, 
  especially if you plan to create a new vectorizer with the same name.
- After dropping a vectorizer, you may want to manually clean up the target table and view if they're no longer needed.
- To ensure that you are dropping the correct vectorizer, keep track of your vectorizer IDs. You can do this by querying 
  the `ai.vectorizer` table.


Examples: 
- Remove the vectorizer with ID 1 and clean up its associated resources:

  ```sql
  -- Assuming we have a vectorizer with ID 1
  SELECT ai.drop_vectorizer(1);
  ```


- Vectorizer reconfiguration: when you want to significantly change the configuration of a vectorizer, it's often easier to drop the old one and create a new one.

  ```sql
  -- Drop the old vectorizer
  SELECT ai.drop_vectorizer(old_vectorizer_id);
  
  -- Create a new vectorizer with different configuration
  SELECT ai.create_vectorizer(
      'my_table'::regclass,
      embedding => ai.embedding_openai('text-embedding-3-large', 1536),  -- Using a different model
      chunking => ai.chunking_character_text_splitter('content', 256, 20),  -- Different chunking
      -- other parameters...
  );
  ```

- Cleanup: when a table or feature is no longer needed, you can remove its associated vectorizer.

- Troubleshooting: if you're experiencing issues with a vectorizer, sometimes it's helpful to drop 
  it and recreate it.

- Resource management: if you need to free up resources such as scheduled job slots, you might drop vectorizers 
  that are no longer actively used.

#### Parameters

`ai.drop_vectorizer` takes the following parameters:

|Name| Type | Default | Required | Description |
|-|------|-|-|-|
|vectorizer_id| int  | -|✔|The identifier of the vectorizer you want to drop|

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

For effective monitoring, you use `ai.vectorizer_status` and `ai.vectorizer_queue_pending` together. 
For example:
```sql
-- First, get an overview of all vectorizers
SELECT * FROM ai.vectorizer_status;

-- Then, if you see a vectorizer with many pending items, you can investigate further
SELECT ai.vectorizer_queue_pending(vectorizer_id_with_many_pending_items);
```

Regular monitoring using these tools helps ensure that your vectorizers are keeping up with data changes, and that 
embeddings remain up-to-date.

The pending items count helps you to:
- Identify bottlenecks in processing.
- Determine if you need to adjust scheduling or processing configurations.
- Monitor the impact of large data imports or updates on your vectorizers.

Available functions are:
- [ai.vectorizer_status](#aivectorizer_status-view): view, monitor and display information about a vectorizer. 
- [ai.vectorizer_queue_pending](#aivectorizer_queue_pending-function): retrieve detailed information about a specific
  vectorizer's queue.


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

- Operational reporting:
   ```sql
   -- Get a daily summary of vectorizer performance
   SELECT 
     id, 
     source_table, 
     pending_items,
     CASE 
       WHEN pending_items = 0 THEN 'Up to date'
       WHEN pending_items < 100 THEN 'Minor backlog'
       WHEN pending_items < 1000 THEN 'Moderate backlog'
       ELSE 'Significant backlog'
     END AS status
   FROM ai.vectorizer_status;
   ```

#### Parameters

`ai.vectorizer_status` does not take any parameters.

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

`ai.vectorizer_queue_pending` enables you to retrieve detailed information about a specific 
vectorizer's queue when you need to focus on a particular vectorizer or troubleshoot issues.

You use `vectorizer_queue_pending` to:
- Retrieve the number of pending items for a specific vectorizer.
- Allow for more granular monitoring of individual vectorizer queues.

#### Example usage

- Return the number of pending items for the vectorizer with ID 1:

  ```sql
  SELECT ai.vectorizer_queue_pending(1);
  ```

- Performance tuning:
   ```sql
   -- Check if recent configuration changes have reduced the backlog
   SELECT ai.vectorizer_queue_pending(vectorizer_id);
   -- Run this query before and after configuration changes to compare
   ```


#### Parameters

`ai.vectorizer_queue_pending function` takes the following parameters:

|Name| Type | Default | Required | Description |
|-|------|-|-|-|
|vectorizer_id| int  | -|✔|The identifier of the vectorizer you want to check|


### Returns

The number of items in the queue for the specified vectorizer


[timescale-cloud]: https://console.cloud.timescale.com/

