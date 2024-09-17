
# Vectorizers

A vectorizer provides users with a powerful and automated way to generate and 
manage LLM embeddings for their PostgreSQL data. Here's a summary of what users 
gain from this feature:

1. Automated Embedding Generation: Users can create a vectorizer for a specified
   table, which automatically generates embeddings for the data in that table.

2. Configurable Embedding Process: The vectorizer is highly configurable, 
   allowing users to specify:
    - The embedding model and dimensions (e.g., OpenAI's text-embedding-3-small)
    - Chunking strategies for text data
    - Formatting templates for combining multiple fields
    - Indexing options for efficient similarity searches
    - Scheduling for background processing

3. Integration with Multiple AI Providers: The vectorizer supports different 
   embedding providers, initially including OpenAI, with more planned for the 
   future.

5. Automatic Updates: The vectorizer creates triggers on the source table, 
   ensuring that embeddings are automatically updated when the source data 
   changes.

6. Efficient Storage and Retrieval: Embeddings are stored in a separate table 
   with appropriate indexing, optimizing for vector similarity searches.

7. Background Processing: The vectorizer can be scheduled to run as a background
   job, minimizing impact on regular database operations.

8. View Creation: A view is automatically created to join the original data with
   its embeddings, making it easy to query and use the embedded data.

9. Scalability: The vectorizer includes options for batch processing and 
   concurrency control, allowing it to handle large datasets efficiently.

10. Fine-grained Access Control: Users can specify which roles should have 
    access to the vectorizer and its related objects.

11. Monitoring and Management: The extension provides functions to monitor the 
    vectorizer's queue, enable/disable scheduling, and manage the vectorizer 
    lifecycle.

This feature significantly simplifies the process of incorporating AI-powered 
semantic search and analysis capabilities into existing PostgreSQL databases, 
making it easier for users to leverage the power of LLMs in their data 
workflows.

Initially, vectorizers only work on the Timescale cloud platform, however 
support for self-hosted installations will be added quickly.


## Creating vectorizers

The `ai.create_vectorizer` function is a key component of the pgai extension's 
vectorizer feature. Its purpose is to set up and configure an automated system 
for generating and managing embeddings for a specified table in the database. 
Here's an explanation of its purpose and usage:

Purpose:
1. Automate the process of creating embeddings for table data
2. Set up necessary infrastructure (tables, views, triggers) for embedding management
3. Configure the embedding generation process according to user specifications
4. Integrate with AI providers for embedding creation
5. Set up scheduling for background processing of embeddings

Usage:
The function takes several parameters to customize the vectorizer:

1. source: The source table (as a regclass) for which embeddings will be generated.
2. embedding: Configuration for the embedding process, using `ai.embedding_openai()` to specify the model and dimensions.
3. chunking: Configuration for how to split text data, using functions like `ai.chunking_character_text_splitter()`.
4. indexing: Specifies how to index the embeddings, e.g., `ai.indexing_diskann()` or `ai.indexing_hnsw()`.
5. formatting: Defines how to format the data before embedding, using `ai.formatting_python_template()`.
6. scheduling: Sets up when and how often to run the vectorizer, e.g., `ai.scheduling_timescaledb()`.
7. processing: Configures how to process the embeddings, like `ai.processing_cloud_functions()`.
8. target_schema, target_table, view_schema, view_name: Optional parameters to specify where to store embeddings and create views.
9. queue_schema, queue_table: Optional parameters for the queue used in background processing.
10. grant_to: An array of role names to grant permissions to.
11. enqueue_existing: Boolean to determine if existing rows should be immediately queued for embedding.

Example usage:
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

This function call would:
1. Set up a vectorizer for the 'website.blog' table
2. Use OpenAI's text-embedding-3-small model to create 768-dimensional embeddings
3. Chunk the 'body' column into 128-character pieces with 10-character overlap
4. Format each chunk with title and published date
5. Schedule the vectorizer to run every 5 minutes starting from a future date
6. Grant necessary permissions to roles 'bob' and 'alice'

The function returns an integer identifier for the created vectorizer, which can
be used in other management functions.

By using `ai.create_vectorizer`, users can quickly set up a sophisticated 
embedding system tailored to their specific needs, without having to manually 
create and manage all the necessary database objects and processes.

## Chunking configuration

The chunking configuration functions in the pgai extension serve the important 
purpose of defining how text data should be split into smaller, manageable 
pieces before being processed for embeddings. This is crucial because many 
embedding models have input size limitations, and chunking allows for processing
of larger text documents while maintaining context.

There are two main chunking functions provided:

1. ai.chunking_character_text_splitter
2. ai.chunking_recursive_character_text_splitter

Let's examine each of these:

1. ai.chunking_character_text_splitter:

Purpose:
- Split text into chunks based on a specified separator
- Control the size of chunks and amount of overlap between chunks

Usage:
```sql
SELECT ai.chunking_character_text_splitter(
    chunk_column name,
    chunk_size int DEFAULT 800,
    chunk_overlap int DEFAULT 400,
    separator text DEFAULT E'\n\n',
    is_separator_regex bool DEFAULT false
)
```

Parameters:
- chunk_column: The name of the column containing the text to be chunked
- chunk_size: Maximum number of characters per chunk
- chunk_overlap: Number of characters to overlap between chunks
- separator: The string or character used to split the text
- is_separator_regex: Whether the separator is a regular expression

Example:
```sql
SELECT ai.chunking_character_text_splitter('body', 128, 10, E'\n;')
```
This would split the 'body' column into chunks of 128 characters, with 10 
character overlap, using '\n;' as the separator.

2. ai.chunking_recursive_character_text_splitter:

Purpose:
- Recursively split text into chunks using multiple separators
- Provides more fine-grained control over the chunking process

Usage:
```sql
SELECT ai.chunking_recursive_character_text_splitter(
    chunk_column name,
    chunk_size int DEFAULT 800,
    chunk_overlap int DEFAULT 400,
    separators text[] DEFAULT array[E'\n\n', E'\n', '.', '?', '!', ' ', ''],
    is_separator_regex bool DEFAULT false
)
```

Parameters:
- chunk_column, chunk_size, chunk_overlap, is_separator_regex: Same as above
- separators: An array of separators to use, applied in order

Example:
```sql
SELECT ai.chunking_recursive_character_text_splitter(
    'content', 
    256, 
    20, 
    separators => array[E'\n;', ' ']
)
```
This would recursively split the 'content' column into chunks of 256 characters,
with 20 character overlap, first trying to split on '\n;', then on spaces.

The key difference between these functions is that the recursive version allows 
for a more sophisticated splitting strategy, potentially preserving more 
semantic meaning in the chunks.

Both of these functions return a JSON configuration object that can be used in 
the `ai.create_vectorizer` function:

```sql
SELECT ai.create_vectorizer(
    'my_table'::regclass,
    chunking => ai.chunking_character_text_splitter('body', 128, 10),
    -- other parameters...
);
```

By using these chunking functions, users can fine-tune how their text data is 
prepared for embedding, ensuring that the chunks are appropriately sized and 
maintain necessary context for their specific use case. This is particularly 
important for maintaining the quality and relevance of the generated embeddings,
especially when dealing with long-form content or documents with specific 
structural elements.

## Embedding configuration

The `ai.embedding_openai` function is a configuration function within the pgai 
extension that specifies settings for using OpenAI's embedding models. Its 
purpose is to create a standardized configuration object that can be used by 
other pgai functions, particularly `ai.create_vectorizer`, to set up embedding 
generation using OpenAI's API.

Purpose:
1. Define which OpenAI embedding model to use
2. Specify the dimensionality of the embeddings
3. Configure optional parameters like the user identifier for API calls
4. Set the name of the environment variable that contains the OpenAI API key

Usage:
The function takes several parameters to customize the OpenAI embedding 
configuration:

1. model (text, required): Specifies the name of the OpenAI embedding model to use, e.g., 'text-embedding-3-small'.
2. dimensions (int, required): Defines the number of dimensions for the embedding vectors. This should match the output dimensions of the chosen model.
3. chat_user (text, optional): An identifier for the user making the API call. This can be useful for tracking API usage or for OpenAI's monitoring purposes.
4. api_key_name (text, optional, default 'OPENAI_API_KEY'): The name of the environment variable that contains the OpenAI API key. This allows for flexible API key management without hardcoding keys in the database.

Example usage:

```sql
SELECT ai.embedding_openai(
    'text-embedding-3-small', 
    768, 
    chat_user => 'bob',
    api_key_name => 'MY_OPENAI_API_KEY'
);
```

This function call would return a JSON configuration object that looks something like this:

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

This configuration object is typically used as an argument to ai.create_vectorizer:

```sql
SELECT ai.create_vectorizer(
    'my_table'::regclass,
    embedding => ai.embedding_openai('text-embedding-3-small', 768),
    -- other parameters...
);
```

By using `ai.embedding_openai`, users can easily specify which OpenAI model they
want to use for generating embeddings, ensure the correct dimensionality is set,
and configure API access details. This function encapsulates the OpenAI-specific
configuration, making it easier to switch between different embedding providers 
or models in the future by using a different configuration function.

The function also provides a layer of abstraction, allowing the pgai extension 
to handle the details of interacting with the OpenAI API based on this 
configuration, simplifying the process for users who may not be familiar with 
the specifics of the OpenAI API.

## Formatting configuration

The `ai.formatting_python_template` function in the pgai extension is used to 
configure how data from the source table should be formatted before being sent 
for embedding. Its primary purpose is to allow users to combine multiple fields 
or add context to the text that will be embedded, which can significantly 
enhance the quality and usefulness of the resulting embeddings.

Purpose:
1. Define a template for formatting the data before embedding
2. Allow combination of multiple fields from the source table
3. Add consistent context or structure to the text being embedded
4. Customize the input for the embedding model to improve relevance and searchability

Usage:
The function takes a single parameter:

```sql
SELECT ai.formatting_python_template(template text DEFAULT '$chunk')
```

Parameter:
- template: A string that defines how the data should be formatted. It uses 
- Python's string formatting syntax with $-prefixed variables.

The function returns a JSON configuration object that can be used in the 
`ai.create_vectorizer` function.

Key points about the template:
1. The $chunk placeholder is required and represents the text chunk that will be embedded.
2. Other placeholders can be used to reference columns from the source table.
3. The template allows for adding static text or structuring the input in a specific way.

Examples:

1. Basic usage (default):
```sql
SELECT ai.formatting_python_template()
```
This uses the default template '$chunk', which simply uses the chunked text as-is.

2. Adding context from other columns:
```sql
SELECT ai.formatting_python_template('Title: $title\nDate: $published\nContent: $chunk')
```
This template adds the title and publication date to each chunk, providing more context for the embedding.

3. Combining multiple fields:
```sql
SELECT ai.formatting_python_template('Author: $author\nCategory: $category\n$chunk')
```
This template prepends author and category information to each chunk.

4. Adding consistent structure:
```sql
SELECT ai.formatting_python_template('BEGIN DOCUMENT\n$chunk\nEND DOCUMENT')
```
This adds start and end markers to each chunk, which could be useful for certain
types of embeddings or retrieval tasks.

Example usage within ai.create_vectorizer:

```sql
SELECT ai.create_vectorizer(
    'blog_posts'::regclass,
    embedding => ai.embedding_openai('text-embedding-3-small', 768),
    chunking => ai.chunking_character_text_splitter('content', 1000, 100),
    formatting => ai.formatting_python_template('Title: $title\nAuthor: $author\nDate: $published\nContent: $chunk'),
    -- other parameters...
);
```

In this example, each chunk of the 'content' column will be formatted with the 
title, author, and publication date before being sent for embedding. This can 
make the embeddings more informative and improve the accuracy of similarity 
searches or other downstream tasks.

The `ai.formatting_python_template` function provides a flexible way to 
structure the input for embedding models, allowing users to incorporate relevant
metadata or add consistent formatting to their text data. This can significantly
enhance the quality and usefulness of the generated embeddings, especially in 
scenarios where context from multiple fields is important for understanding or 
searching the content.

## Indexing configuration

The indexing configuration functions in the pgai extension are designed to 
specify how the generated embeddings should be indexed for efficient similarity 
searches. These functions allow users to choose and configure the indexing 
method that best suits their needs in terms of performance, accuracy, and 
resource usage. Let's examine each of these functions:

1. ai.indexing_none

Purpose:
- Specify that no special indexing should be used for the embeddings.
- Useful when you don't need fast similarity searches or when you're dealing 
  with a small amount of data.

Usage:
```sql
SELECT ai.indexing_none()
```

This function takes no parameters and simply returns a configuration object 
indicating that no indexing should be used.

2. ai.indexing_diskann

Purpose:
- Configure indexing using the DiskANN algorithm, which is designed for high-performance approximate nearest neighbor search on large-scale datasets.
- Suitable for very large datasets that need to be stored on disk.

Usage:
```sql
SELECT ai.indexing_diskann(
    min_rows int DEFAULT 100000,
    storage_layout text DEFAULT null,
    num_neighbors int DEFAULT null,
    search_list_size int DEFAULT null,
    max_alpha float8 DEFAULT null,
    num_dimensions int DEFAULT null,
    num_bits_per_dimension int DEFAULT null
)
```

Parameters:
- min_rows: Minimum number of rows before creating the index
- storage_layout: Can be 'memory_optimized' or 'plain'
- num_neighbors, search_list_size, max_alpha, num_dimensions, num_bits_per_dimension: Advanced DiskANN parameters

Example:
```sql
SELECT ai.indexing_diskann(min_rows => 500000, storage_layout => 'memory_optimized')
```

3. ai.indexing_hnsw

Purpose:
- Configure indexing using the Hierarchical Navigable Small World (HNSW) algorithm, which is known for fast and accurate approximate nearest neighbor search.
- Suitable for in-memory datasets and scenarios where query speed is crucial.

Usage:
```sql
SELECT ai.indexing_hnsw(
    min_rows int DEFAULT 100000,
    opclass text DEFAULT 'vector_cosine_ops',
    m int DEFAULT null,
    ef_construction int DEFAULT null
)
```

Parameters:
- min_rows: Minimum number of rows before creating the index
- opclass: The operator class for the index ('vector_cosine_ops', 'vector_l2_ops', or 'vector_ip_ops')
- m, ef_construction: Advanced HNSW parameters

Example:
```sql
SELECT ai.indexing_hnsw(min_rows => 50000, opclass => 'vector_l2_ops')
```

Usage in ai.create_vectorizer:

These indexing configuration functions are typically used as arguments to the 
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

Key points about indexing:

1. The choice of indexing method depends on your dataset size, query performance requirements, and available resources.

2. DiskANN is generally better for very large datasets that don't fit in memory, while HNSW is often faster for in-memory datasets.

3. The 'min_rows' parameter allows you to delay index creation until you have enough data to justify the overhead.

4. No index (ai.indexing_none) might be suitable for small datasets or when you're more concerned with insertion speed than query speed.

5. These indexing methods are designed for approximate nearest neighbor search, which trades a small amount of accuracy for significant speed improvements in similarity searches.

By providing these indexing options, pgai allows users to optimize their 
embedding storage and retrieval based on their specific use case and performance
requirements. This flexibility is crucial for scaling AI-powered search and 
analysis capabilities within a PostgreSQL database.

## Scheduling configuration

The scheduling functions in the pgai extension are designed to configure when 
and how often the vectorizer should run to process new or updated data. These 
functions allow users to set up automated, periodic execution of the embedding 
generation process. Let's examine each of these functions:

1. ai.scheduling_none

Purpose:
- Specify that no automatic scheduling should be set up for the vectorizer.
- Useful when you want to manually control when the vectorizer runs or when you're using an external scheduling system.

Usage:
```sql
SELECT ai.scheduling_none()
```

This function takes no parameters and simply returns a configuration object 
indicating that no scheduling should be used.

2. ai.scheduling_timescaledb

Purpose:
- Configure automated scheduling using TimescaleDB's job scheduling system.
- Allow periodic execution of the vectorizer to process new or updated data.
- Provide fine-grained control over when and how often the vectorizer runs.

Usage:
```sql
SELECT ai.scheduling_timescaledb(
    schedule_interval interval DEFAULT interval '10m',
    initial_start timestamptz DEFAULT null,
    fixed_schedule bool DEFAULT null,
    timezone text DEFAULT null
)
```

Parameters:
- schedule_interval: How often the vectorizer should run (default is every 10 minutes)
- initial_start: When the first run should occur (optional)
- fixed_schedule: Whether to use a fixed schedule (true) or a sliding window (false)
- timezone: The timezone for the schedule (optional)

Examples:

1. Basic usage (run every 10 minutes):
```sql
SELECT ai.scheduling_timescaledb()
```

2. Custom interval (run every hour):
```sql
SELECT ai.scheduling_timescaledb(interval '1 hour')
```

3. Specific start time and timezone:
```sql
SELECT ai.scheduling_timescaledb(
    interval '30 minutes',
    initial_start => '2023-12-01 00:00:00'::timestamptz,
    timezone => 'America/New_York'
)
```

4. Fixed schedule:
```sql
SELECT ai.scheduling_timescaledb(
    interval '1 day',
    fixed_schedule => true,
    timezone => 'UTC'
)
```

Usage in `ai.create_vectorizer`:

These scheduling configuration functions are typically used as arguments to the 
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

Key points about scheduling:

1. ai.scheduling_none is useful when you want manual control over when the vectorizer runs.

2. ai.scheduling_timescaledb leverages TimescaleDB's robust job scheduling system, which is designed for reliability and scalability.

3. The schedule_interval determines how frequently the vectorizer checks for new or updated data to process.

4. The initial_start parameter allows you to delay the start of scheduling, which can be useful for coordinating with other system processes or maintenance windows.

5. The fixed_schedule option determines whether the job runs at fixed times (e.g., every day at midnight) or on a sliding window (e.g., every 24 hours from the last run).

6. The timezone parameter ensures that schedules are interpreted correctly, especially important for fixed schedules or when coordinating with business hours.

By providing these scheduling options, pgai allows users to automate the process
of keeping their embeddings up-to-date with minimal manual intervention. This is
crucial for maintaining the relevance and accuracy of AI-powered search and 
analysis capabilities, especially in systems where data is frequently updated or
added. The flexibility in scheduling also allows users to balance the freshness 
of embeddings against system resource usage and other operational 
considerations.

## Enabling/Disabling vectorizer schedules

The `ai.enable_vectorizer_schedule` and `ai.disable_vectorizer_schedule` 
functions are management tools in the pgai extension that allow users to control
the execution of scheduled vectorizer jobs. These functions provide a way to 
temporarily pause or resume the automatic processing of embeddings without 
having to delete or recreate the vectorizer configuration. Let's examine each of 
these functions:

1. ai.enable_vectorizer_schedule

Purpose:
- Activate or reactivate the scheduled job for a specific vectorizer.
- Allow the vectorizer to resume automatic processing of new or updated data.

Usage:
```sql
SELECT ai.enable_vectorizer_schedule(vectorizer_id int)
```

Parameter:
- vectorizer_id: The identifier of the vectorizer whose schedule you want to enable.

2. ai.disable_vectorizer_schedule

Purpose:
- Deactivate the scheduled job for a specific vectorizer.
- Temporarily stop the automatic processing of new or updated data.

Usage:
```sql
SELECT ai.disable_vectorizer_schedule(vectorizer_id int)
```

Parameter:
- vectorizer_id: The identifier of the vectorizer whose schedule you want to disable.

Example usage:

1. Disabling a vectorizer schedule:
```sql
SELECT ai.disable_vectorizer_schedule(1);
```
This would stop the automatic scheduling for the vectorizer with ID 1.

2. Enabling a vectorizer schedule:
```sql
SELECT ai.enable_vectorizer_schedule(1);
```
This would resume the automatic scheduling for the vectorizer with ID 1.

Key points about these functions:

1. They provide fine-grained control over individual vectorizer schedules without affecting other vectorizers or the overall system configuration.

2. Disabling a schedule does not delete the vectorizer or its configuration; it simply stops the automatic execution of the job.

3. These functions are particularly useful in scenarios such as:
    - System maintenance windows where you want to reduce database load
    - Temporarily pausing processing during data migrations or large bulk updates
    - Debugging or troubleshooting issues related to the vectorizer
    - Implementing manual control over when embeddings are updated

4. When a schedule is disabled, new or updated data will not be automatically processed. However, the data will still be queued, and will be processed when the schedule is re-enabled or when the vectorizer is manually run.

5. These functions only affect vectorizers that use scheduled processing (i.e., those configured with ai.scheduling_timescaledb). Vectorizers configured with ai.scheduling_none are not affected.

6. After re-enabling a schedule, the next run will occur based on the original scheduling configuration (e.g., if it was set to run every hour, it will run at the next hour mark after being enabled).

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

These functions provide an important layer of operational control for managing 
pgai vectorizers in production environments. They allow database administrators 
and application developers to balance the need for up-to-date embeddings with 
other system priorities and constraints, enhancing the overall flexibility and 
manageability of the pgai extension.

## Processing configuration

The processing configuration functions in the pgai extension are used to specify 
how the vectorizer should process data when generating embeddings. These 
functions allow users to choose between different processing strategies, 
balancing factors like performance, scalability, and infrastructure 
requirements. Let's examine each of these functions:

1. ai.processing_none

Purpose:
- Indicate that no special processing configuration is needed.
- Use the default in-database processing for generating embeddings.

Usage:
```sql
SELECT ai.processing_none()
```

This function takes no parameters and returns a configuration object indicating 
that default processing should be used.

2. ai.processing_cloud_functions

Purpose:
- Configure the vectorizer to use cloud functions for processing embeddings.
- Enable distributed and scalable processing of embeddings outside the database.
- Allow for potential performance improvements and reduced load on the database server.

Usage:
```sql
SELECT ai.processing_cloud_functions(
    batch_size int DEFAULT null,
    concurrency int DEFAULT null
)
```

Parameters:
- batch_size: The number of items to process in each batch (optional, default determined by the system)
- concurrency: The number of concurrent processing tasks to run (optional, default determined by the system)

Examples:

1. Basic usage (use system defaults):
```sql
SELECT ai.processing_cloud_functions()
```

2. Specifying batch size:
```sql
SELECT ai.processing_cloud_functions(batch_size => 100)
```

3. Specifying both batch size and concurrency:
```sql
SELECT ai.processing_cloud_functions(batch_size => 50, concurrency => 5)
```

Usage in `ai.create_vectorizer`:

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

Key points about these processing functions:

1. ai.processing_none:
    - Uses the default in-database processing.
    - Suitable for smaller datasets or when you want to keep all processing within the database.
    - Simpler setup as it doesn't require additional infrastructure.

2. ai.processing_cloud_functions:
    - Enables distributed processing using cloud functions.
    - Can improve performance and scalability, especially for large datasets.
    - Reduces load on the database server by offloading embedding generation.
    - Requires additional setup and infrastructure for cloud functions.
    - Allows for fine-tuning of batch size and concurrency to optimize performance.

3. The batch_size parameter in ai.processing_cloud_functions:
    - Controls how many items are processed in each cloud function invocation.
    - Larger batch sizes can improve efficiency but may increase memory usage.
    - The optimal batch size depends on your data and cloud function configuration.

4. The concurrency parameter in ai.processing_cloud_functions:
    - Determines how many cloud functions can run simultaneously.
    - Higher concurrency can speed up processing but may increase costs and resource usage.
    - The optimal concurrency depends on your cloud infrastructure and rate limits.

5. When using ai.processing_cloud_functions, you need to ensure that:
    - Your cloud functions are properly set up and configured.
    - The database can communicate with the cloud function service.
    - You have considered security implications of sending data to cloud functions.

By providing these processing options, pgai allows users to choose the most appropriate strategy for their specific use case, infrastructure, and performance requirements. The ai.processing_none option offers simplicity and keeps everything within the database, while ai.processing_cloud_functions provides a way to scale out the embedding generation process for larger datasets or higher throughput requirements.

## Dropping a vectorizer

The ai.drop_vectorizer function is a management tool in the pgai extension 
designed to remove a previously created vectorizer and clean up associated 
resources. Its primary purpose is to provide a controlled way to delete a 
vectorizer when it's no longer needed or when you want to reconfigure it from 
scratch.

Purpose:
1. Remove a specific vectorizer configuration from the system.
2. Clean up associated database objects and scheduled jobs.
3. Provide a safe way to undo the creation of a vectorizer.

Usage:
```sql
SELECT ai.drop_vectorizer(vectorizer_id int)
```

Parameter:
- vectorizer_id: The identifier of the vectorizer you want to drop.

This function doesn't return a value, but it performs several cleanup operations.

Key actions performed by ai.drop_vectorizer:

1. Deletes the scheduled job associated with the vectorizer (if any).
2. Drops the trigger from the source table that was used to queue changes.
3. Drops the trigger function that backed the source table trigger.
4. Drops the queue table used for managing updates to be processed.
5. Deletes the vectorizer row from the ai.vectorizer table.

Important notes:

1. It does NOT drop the target table containing the embeddings.
2. It does NOT drop the view joining the target and source tables.

This design allows you to keep the generated embeddings and the convenient view 
even after dropping the vectorizer, which can be useful if you want to stop 
automatic updates but still use the existing embeddings.

Example usage:

```sql
-- Assuming we have a vectorizer with ID 1
SELECT ai.drop_vectorizer(1);
```

This would remove the vectorizer with ID 1 and clean up its associated resources.

Typical scenarios for using ai.drop_vectorizer:

1. Reconfiguration: When you want to significantly change the configuration of a vectorizer, it's often easier to drop the old one and create a new one.

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

2. Cleanup: When a table or feature is no longer needed, you can remove its associated vectorizer.

3. Troubleshooting: If you're experiencing issues with a vectorizer, sometimes it's helpful to drop it and recreate it.

4. Resource management: If you need to free up resources (like scheduled job slots), you might drop vectorizers that are no longer actively used.

Best practices:

1. Before dropping a vectorizer, ensure that you won't need the automatic embedding updates it provides.
2. If you want to preserve the embeddings, make sure to backup or rename the target table before dropping the vectorizer, especially if you plan to create a new vectorizer with the same name.
3. After dropping a vectorizer, you may want to manually clean up the target table and view if they're no longer needed.
4. Keep track of your vectorizer IDs, possibly by querying the ai.vectorizer table, to ensure you're dropping the correct one.

The ai.drop_vectorizer function provides a clean way to remove vectorizers from 
your system, allowing for easy management and reconfiguration of your 
AI-enhanced database setup. It's an important tool for maintaining and evolving 
your pgai-powered applications over time.

## Viewing vectorizer status

The ai.vectorizer_status view and the ai.vectorizer_queue_pending function are 
monitoring tools in the pgai extension that provide insights into the state and 
performance of vectorizers. Let's examine each of these:

1. ai.vectorizer_status view

Purpose:
- Provide a high-level overview of all vectorizers in the system
- Display key information about each vectorizer's configuration and current state
- Offer a quick way to check the status of pending items for each vectorizer

Usage:
```sql
SELECT * FROM ai.vectorizer_status;
```

Columns:
- id: The unique identifier of the vectorizer
- source_table: The fully qualified name of the source table
- target_table: The fully qualified name of the table storing the embeddings
- view: The fully qualified name of the view joining source and target tables
- pending_items: The number of items waiting to be processed by the vectorizer

Example:
```sql
SELECT * FROM ai.vectorizer_status WHERE pending_items > 0;
```
This query would show all vectorizers that have items waiting to be processed.

2. ai.vectorizer_queue_pending function

Purpose:
- Provide a detailed count of pending items for a specific vectorizer
- Allow for more granular monitoring of individual vectorizer queues

Usage:
```sql
SELECT ai.vectorizer_queue_pending(vectorizer_id int) RETURNS bigint
```

Parameter:
- vectorizer_id: The identifier of the vectorizer you want to check

Returns:
- The number of items in the queue for the specified vectorizer

Example:
```sql
SELECT ai.vectorizer_queue_pending(1);
```
This would return the number of pending items for the vectorizer with ID 1.

Key points about these monitoring tools:

1. The ai.vectorizer_status view:
    - Provides a comprehensive overview of all vectorizers in one query
    - Useful for regular monitoring and health checks of the entire system
    - The pending_items column gives a quick indication of processing backlogs

2. The ai.vectorizer_queue_pending function:
    - Offers more detailed information about a specific vectorizer's queue
    - Useful when you need to focus on a particular vectorizer or troubleshoot issues

3. These tools can be used together for effective monitoring:
   ```sql
   -- First, get an overview of all vectorizers
   SELECT * FROM ai.vectorizer_status;
   
   -- Then, if you see a vectorizer with many pending items, you can investigate further
   SELECT ai.vectorizer_queue_pending(vectorizer_id_with_many_pending_items);
   ```

4. The pending items count can help you:
    - Identify bottlenecks in processing
    - Determine if you need to adjust scheduling or processing configurations
    - Monitor the impact of large data imports or updates on your vectorizers

5. Regular monitoring using these tools can help ensure that your vectorizers are keeping up with data changes and that embeddings remain up-to-date.

Use cases:

1. System health monitoring:
   ```sql
   -- Alert if any vectorizer has more than 1000 pending items
   SELECT id, source_table, pending_items 
   FROM ai.vectorizer_status 
   WHERE pending_items > 1000;
   ```

2. Performance tuning:
   ```sql
   -- Check if recent configuration changes have reduced the backlog
   SELECT ai.vectorizer_queue_pending(vectorizer_id);
   -- Run this query before and after configuration changes to compare
   ```

3. Operational reporting:
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

These monitoring tools are crucial for maintaining the health and performance of 
your pgai-enhanced database. They allow you to proactively manage your 
vectorizers, ensure timely processing of embeddings, and quickly identify and 
address any issues that may arise in your AI-powered data pipelines.
