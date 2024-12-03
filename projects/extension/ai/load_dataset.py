import json
import datasets
from typing import Optional, Dict, Any

from .utils import get_guc_value

GUC_DATASET_CACHE_DIR = "ai.dataset_cache_dir"


def get_default_column_type(dtype):
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


def get_column_info(dataset, field_types):
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
    plpy, name, config_name, schema, table_name, column_types, if_table_exists
):
    # Generate default table name if not provided
    if table_name is None:
        # Handle potential nested dataset names (e.g., "huggingface/dataset")
        base_name = name.split("/")[-1]
        # Add config name to table name if present
        if config_name:
            base_name = f"{base_name}_{config_name}"
        # Replace any non-alphanumeric characters with underscore
        table_name = "".join(c if c.isalnum() else "_" for c in base_name.lower())

    # Construct fully qualified table name
    qualified_table = f'"{schema}"."{table_name}"'

    # Check if table exists
    plan = plpy.prepare(
        """
        SELECT pg_catalog.to_regclass(pg_catalog.format('%I.%I', $1, $2)) is not null as exists
    """,
        ["text", "text"],
    )
    result = plan.execute([schema, table_name], 1)
    table_exists = result[0]["exists"]

    if table_exists:
        if if_table_exists == "drop":
            plpy.execute(f"DROP TABLE IF EXISTS {qualified_table}")
        elif if_table_exists == "error":
            plpy.error(
                f"Table {qualified_table} already exists. Set if_table_exists to 'drop' to replace it or 'append' to add to it."
            )
        elif if_table_exists == "append":
            return qualified_table
        else:
            plpy.error(f"Unsupported if_table_exists value: {if_table_exists}")

    column_type_def = ", ".join(
        f'"{name}" {col_type}' for name, col_type in column_types.items()
    )

    # Create table
    plpy.execute(f"CREATE TABLE {qualified_table} ({column_type_def})")
    return qualified_table


def load_dataset(
    plpy,
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

            num_rows += len(batch_arrays[0])
            batch_count += 1
            insert_plan.execute(batch_arrays)
    return num_rows
