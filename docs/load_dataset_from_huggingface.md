# Load dataset from Hugging Face

The `ai.load_dataset` function allows you to load datasets from Hugging Face's datasets library directly into your PostgreSQL database.

## Example Usage

```sql
select ai.load_dataset('squad');

select * from squad limit 10;
```

## Parameters
| Name          | Type    | Default     | Required | Description                                                                                        |
|---------------|---------|-------------|----------|----------------------------------------------------------------------------------------------------|
| name          | text    | -           | ✔        | The name of the dataset on Hugging Face (e.g., 'squad', 'glue', etc.)                             |
| config_name   | text    | -           | ✖        | The specific configuration of the dataset to load. See [Hugging Face documentation](https://huggingface.co/docs/datasets/v2.20.0/en/load_hub#configurations) for more information.                                                  |
| split         | text    | -           | ✖        | The split of the dataset to load (e.g., 'train', 'test', 'validation'). Defaults to all splits.   |
| schema_name   | text    | 'public'    | ✖        | The PostgreSQL schema where the table will be created                                             |
| table_name    | text    | -           | ✖        | The name of the table to create. If null, will use the dataset name                               |
| if_table_exists| text   | 'error'     | ✖        | Behavior when table exists: 'error' (raise error), 'append' (add rows), 'drop' (drop table and recreate) |
| field_types   | jsonb   | -           | ✖        | Custom PostgreSQL data types for columns as a JSONB dictionary from name to type.                 |
| batch_size    | int     | 5000        | ✖        | Number of rows to insert in each batch                                                            |
| max_batches   | int     | null        | ✖        | Maximum number of batches to load. Null means load all                                            |
| kwargs        | jsonb   | -           | ✖        | Additional arguments passed to the Hugging Face dataset loading function                           |

## Returns

Returns the number of rows loaded into the database (bigint).

## Examples

1. Basic usage - Load the entire 'squad' dataset:

```sql
SELECT ai.load_dataset('squad');
```

The data is loaded into a table named `squad`.

2. Load a small subset of the 'squad' dataset:

```sql
SELECT ai.load_dataset('squad', batch_size => 100, max_batches => 1);
```

3. Load specific configuration and split:

```sql
SELECT ai.load_dataset(
    name => 'glue',
    config_name => 'mrpc',
    split => 'train'
);
```

4. Load with custom table name and field types:

```sql
SELECT ai.load_dataset(
    name => 'glue',
    config_name => 'mrpc',
    table_name => 'mrpc',
    field_types => '{"sentence1": "text", "sentence2": "text"}'::jsonb
);
```

5. Pre-create the table and load data into it:

```sql

CREATE TABLE squad (
    id          TEXT,
    title       TEXT,
    context     TEXT,
    question    TEXT,
    answers     JSONB
);

SELECT ai.load_dataset(
    name => 'squad',
    table_name => 'squad',
    if_table_exists => 'append'
);
```

## Notes

- The function requires an active internet connection to download datasets from Hugging Face.
- Large datasets may take significant time to load depending on size and connection speed.
- The function automatically maps Hugging Face dataset types to appropriate PostgreSQL data types unless overridden by `field_types`.
