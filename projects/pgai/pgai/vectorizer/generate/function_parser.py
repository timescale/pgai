from dataclasses import dataclass

import psycopg


@dataclass
class PostgresParameter:
    name: str
    type_name: str
    is_array: bool = False
    is_required: bool = False

    @property
    def python_type(self) -> str:
        """Convert Postgres type to Python type."""
        type_mapping = {
            "text": "str",
            "name": "str",
            "int4": "int",
            "int8": "int",
            "bool": "bool",
            "boolean": "bool",
            "jsonb": "dict[str, Any]",
            "float8": "float",
            "interval": "timedelta",
            "timestamptz": "datetime",
            "_text": "list[str]",
            "_int4": "list[int]",
            "_float8": "list[float]",
            "regclass": "str",
        }
        base_type = type_mapping.get(self.type_name, "Any")
        if self.is_array and not base_type.startswith("list"):
            type_str = f"list[{base_type}]"
        else:
            type_str = base_type
        if not self.is_required:
            type_str = f"{type_str} | None"
        return type_str


@dataclass
class PostgresFunction:
    name: str
    schema: str
    parameters: list[PostgresParameter]
    return_type: str


def get_function_metadata(
    conn: psycopg.Connection, function_names: list[str]
) -> list[PostgresFunction]:
    """Extract function metadata from Postgres catalog."""

    query = """
        SELECT
            p.proname,
            n.nspname,
            p.proargnames,
            p.pronargdefaults,
            string_to_array(array_to_string(p.proargtypes, ' '), ' ') as argtypes,
            p.proallargtypes,
            p.proargmodes,
            t.typname as return_type,
            p.oid,
            p.proargnames IS NULL as null_argnames,
            p.proargtypes IS NULL as null_argtypes
        FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        JOIN pg_type t ON p.prorettype = t.oid
        WHERE n.nspname = 'ai'
          AND p.proname = ANY(%s)
        ORDER BY p.proname;
    """

    functions: list[PostgresFunction] = []
    with conn.cursor() as cur:
        cur.execute(query, (function_names,))

        results = cur.fetchall()
        for row in results:
            parameters: list[PostgresParameter] = []
            param_names = row[2] or []  # type: ignore
            count_of_default_params = row[3]
            param_count = len(param_names)  # type: ignore
            non_default_count = param_count - count_of_default_params
            param_types = row[4] or []  # type: ignore

            for i, name in enumerate(param_names):  # type: ignore
                type_oid = int(param_types[i]) if i < len(param_types) else None  # type: ignore

                # Get detailed type info
                type_query = """
                    SELECT t.typname,
                           (CASE WHEN t.typtype = 'b' THEN t.typname
                                WHEN t.typtype = 'a' THEN (SELECT at.typname
                                                         FROM pg_type at
                                                         WHERE at.oid = t.typelem)
                                ELSE t.typname
                            END) as base_type,
                           t.typtype = 'a' as is_array
                    FROM pg_type t
                    WHERE t.oid = %s
                """
                cur.execute(type_query, (type_oid,))
                type_info = cur.fetchone()

                type_name = type_info[1]  # type: ignore
                is_array = type_info[2]  # type: ignore

                # A parameter is required if it has no default value
                is_required = i < non_default_count

                parameters.append(
                    PostgresParameter(
                        name=name,  # type: ignore
                        type_name=type_name,  # type: ignore
                        is_array=is_array,  # type: ignore
                        is_required=is_required,
                    )
                )

            functions.append(
                PostgresFunction(
                    name=f"ai.{row[0]}",
                    schema=row[1],
                    parameters=parameters,
                    return_type=row[7],
                )
            )

    return functions


@dataclass
class VectorizerParameter:
    """Dataclass to specifically handle create_vectorizer function parameters"""

    name: str
    python_type: str
    accepted_configs: list[str] | None = None
    is_required: bool = False


def read_create_vectorizer_metadata(
    conn: psycopg.Connection,
) -> list[VectorizerParameter]:
    """Extract and enhance metadata for the create_vectorizer function parameters"""
    # First get basic function metadata
    functions = get_function_metadata(conn, ["create_vectorizer"])
    if not functions:
        raise ValueError("create_vectorizer function not found")

    vectorizer_fn = functions[0]

    # Map parameter names to their enhanced metadata
    parameters: list[VectorizerParameter] = []

    # Query to get all configuration functions for each argument type
    config_functions_query = """
    SELECT p.proname
    FROM pg_proc p
    JOIN pg_namespace n ON p.pronamespace = n.oid
    WHERE n.nspname = 'ai'
    AND p.proname LIKE %s;
    """

    for param in vectorizer_fn.parameters:
        # Skip internal parameters that shouldn't be exposed
        if param.name.startswith("_"):
            continue

        accepted_configs = None
        python_type = param.python_type

        # For each parameter, check if there is corresponding config functions
        with conn.cursor() as cur:
            cur.execute(config_functions_query, (f"{param.name}_%",))
            config_functions = [row[0] for row in cur.fetchall()]

            if config_functions:
                # Convert function names to config class names
                accepted_configs = [
                    f"{''.join(part.title() for part in name.split('_'))}Config"
                    for name in config_functions
                ]
                # Create union type of all possible configs
                python_type = " | ".join(accepted_configs) + " | None"

        parameters.append(
            VectorizerParameter(
                name=param.name,
                python_type=python_type,
                accepted_configs=accepted_configs,
                is_required=param.is_required,
            )
        )

    return parameters
