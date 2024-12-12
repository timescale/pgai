import json
import datasets
from typing import Optional, Dict, Any

from .utils import get_guc_value

GUC_DATASET_CACHE_DIR = "ai.dataset_cache_dir"


def byte_size(s):
    return len(s.encode("utf-8"))


def get_default_column_type(dtype: str) -> str:
    # Default type mapping from dtypes to PostgreSQL types
    type_mapping = {
        "string": "TEXT",
        "dict": "JSONB",
        "list": "JSONB",
        "int64": "INT8",
        "int32": "INT4",
        "int16": "INT2",
        "int8": "INT2",
        "float64": "FLOAT8",
        "float32": "FLOAT4",
        "float16": "FLOAT4",
        "bool": "BOOLEAN",
    }

    if dtype.startswith("timestamp"):
        return "TIMESTAMPTZ"
    else:
        return type_mapping.get(dtype.lower(), "TEXT")


def get_column_info(
    dataset: datasets.Dataset, field_types: Optional[Dict[str, str]]
) -> tuple[Dict[str, str], Dict[str, Any], str]:
    # Extract types from features
    column_dtypes = {name: feature.dtype for name, feature in dataset.features.items()}
    # Prepare column types, using field_types if provided, otherwise use inferred types
    column_pgtypes = {}
    for name, py_type in column_dtypes.items():
        # Use custom type if provided, otherwise map from python type
        column_pgtypes[name] = (
            field_types.get(name)
            if field_types and name in field_types
            else get_default_column_type(str(py_type))
        )
    column_names = ", ".join(f'"{name}"' for name in column_dtypes.keys())
    return column_pgtypes, column_dtypes, column_names


def create_table(
    plpy: Any,
    name: str,
    config_name: Optional[str],
    schema: str,
    table_name: Optional[str],
    column_types: Dict[str, str],
    if_table_exists: str,
) -> str:
    # Generate default table name if not provided
    if table_name is None:
        # Handle potential nested dataset names (e.g., "huggingface/dataset")
        base_name = name.split("/")[-1]
        # Add config name to table name if present
        if config_name:
            base_name = f"{base_name}_{config_name}"
        # Replace any non-alphanumeric characters with underscore
        table_name = "".join(c if c.isalnum() else "_" for c in base_name.lower())

        # Check table name length - PostgreSQL has a 63 character limit for identifiers
        if byte_size(table_name) > 63:
            # Find the last underscore before the 63 character limit
            last_underscore = table_name[:63].rstrip("_").rfind("_")
            if last_underscore > 0:
                table_name = table_name[:last_underscore]
            else:
                # If no underscore found, just truncate
                table_name = table_name[:63]
    else:
        # table_name is provided by the user
        # Check table name length - PostgreSQL has a 63 character limit for identifiers
        if byte_size(table_name) > 63:
            plpy.error(
                f"Table name '{table_name}' exceeds PostgreSQL's 63 character limit"
            )

    # Construct fully qualified table name
    plan = plpy.prepare(
        """
        SELECT pg_catalog.format('%I.%I', $1, $2) as qualified_table_name
    """,
        ["text", "text"],
    )
    result = plan.execute([schema, table_name], 1)
    qualified_table = result[0]["qualified_table_name"]

    # Check if table exists
    result = plpy.execute(
        f"""
        SELECT pg_catalog.to_regclass('{qualified_table}')::text as friendly_table_name
        """
    )
    friendly_table_name = result[0]["friendly_table_name"]
    table_exists = friendly_table_name is not None

    if table_exists:
        if if_table_exists == "drop":
            plpy.notice(f"dropping and recreating table {friendly_table_name}")
            plpy.execute(f"DROP TABLE IF EXISTS {qualified_table}")
        elif if_table_exists == "error":
            plpy.error(
                f"Table {friendly_table_name} already exists. Set if_table_exists to 'drop' to replace it or 'append' to add to it."
            )
        elif if_table_exists == "append":
            plpy.notice(f"adding data to the existing {friendly_table_name} table")
            return qualified_table
        else:
            plpy.error(f"Unsupported if_table_exists value: {if_table_exists}")
    else:
        plpy.notice(f"creating table {qualified_table}")

    column_type_def = ", ".join(
        f'"{name}" {col_type}' for name, col_type in column_types.items()
    )

    # Create table
    plpy.execute(f"CREATE TABLE {qualified_table} ({column_type_def})")
    return qualified_table


def load_dataset(
    plpy: Any,
    # Dataset loading parameters
    name: str,
    config_name: Optional[str] = None,
    split: Optional[str] = None,
    # Database target parameters
    schema: str = "public",
    table_name: Optional[str] = None,
    if_table_exists: str = "error",
    # Advanced options
    field_types: Optional[Dict[str, str]] = None,
    batch_size: int = 5000,
    max_batches: Optional[int] = None,
    commit_every_n_batches: Optional[int] = None,
    # Additional dataset loading options
    **kwargs: Dict[str, Any],
) -> int:
    """
    Load a dataset into PostgreSQL database using plpy with batch UNNEST operations.

    Args:
        # Dataset loading parameters
        name: Name of the dataset
        config_name: Configuration name to load. Some datasets have multiple configurations
            (versions or subsets) available. See: https://huggingface.co/docs/datasets/v2.20.0/en/load_hub#configurations
        split: Dataset split to load (defaults to all splits)
        cache_dir: Directory to cache downloaded datasets (default: None)

        # Database target parameters
        schema: Target schema name (default: "public")
        table_name: Target table name (default: derived from dataset name)
        drop_if_exists: If True, drop existing table; if False, error if table exists (default: False)

        # Advanced options
        field_types: Optional dictionary of field names to PostgreSQL types
        batch_size: Number of rows to insert in each batch (default: 5000)

        # Additional dataset loading options
        **kwargs: Additional keyword arguments passed to datasets.load_dataset()

    Returns:
        Number of rows loaded
    """

    cache_dir = get_guc_value(plpy, GUC_DATASET_CACHE_DIR, None)

    # Load dataset using Hugging Face datasets library
    ds = datasets.load_dataset(
        name, config_name, split=split, cache_dir=cache_dir, streaming=True, **kwargs
    )
    if isinstance(ds, datasets.IterableDatasetDict):
        datasetdict = ds
    elif isinstance(ds, datasets.IterableDataset):
        datasetdict = {split: ds}
    else:
        plpy.error(
            f"Unsupported dataset type: {type(ds)}. Only datasets.IterableDatasetDict and datasets.IterableDataset are supported."
        )

    first_dataset = next(iter(datasetdict.values()))
    column_pgtypes, column_dtypes, column_names = get_column_info(
        first_dataset, field_types
    )
    qualified_table = create_table(
        plpy, name, config_name, schema, table_name, column_pgtypes, if_table_exists
    )

    # Prepare the UNNEST parameters and INSERT statement once
    unnest_params = []
    type_params = []
    for i, (col_name, col_type) in enumerate(column_pgtypes.items(), 1):
        unnest_params.append(f"${i}::{col_type}[]")
        type_params.append(f"{col_type}[]")

    insert_sql = f"""
        INSERT INTO {qualified_table} ({column_names})
        SELECT * FROM unnest({', '.join(unnest_params)})
    """
    insert_plan = plpy.prepare(insert_sql, type_params)

    num_rows = 0
    batch_count = 0
    batches_since_commit = 0
    for split, dataset in datasetdict.items():
        # Process data in batches using dataset iteration
        batched_dataset = dataset.batch(batch_size=batch_size)
        for batch in batched_dataset:
            if max_batches and batch_count >= max_batches:
                break

            batch_arrays = [[] for _ in column_dtypes]
            for i, (col_name, py_type) in enumerate(column_dtypes.items()):
                type_str = str(py_type).lower()
                array_values = batch[col_name]

                if type_str in ("dict", "list"):
                    batch_arrays[i] = [json.dumps(value) for value in array_values]
                elif type_str in ("int64", "int32", "int16", "int8"):
                    batch_arrays[i] = [int(value) for value in array_values]
                elif type_str in ("float64", "float32", "float16"):
                    batch_arrays[i] = [float(value) for value in array_values]
                else:
                    batch_arrays[i] = array_values

            insert_plan.execute(batch_arrays)
            num_rows += len(batch_arrays[0])
            batch_count += 1
            batches_since_commit += 1
            plpy.debug(
                f"inserted {num_rows} rows using {batch_count} batches into {qualified_table} so far..."
            )
            if (
                commit_every_n_batches
                and batches_since_commit >= commit_every_n_batches
            ):
                plpy.commit()
                batches_since_commit = 0

    return num_rows
