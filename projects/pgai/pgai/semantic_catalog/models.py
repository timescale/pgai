from typing import Literal

from pydantic import BaseModel


class ObjectDescription(BaseModel):
    """Model representing a description of a database object.

    This class represents the metadata and description of database objects such as
    tables, views, functions, etc. It includes identifiers that can be used to
    locate the object in the database, as well as a textual description.

    Attributes:
        id: Semantic catalog ID (default: -1 if not assigned).
        classid: PostgreSQL object class ID (for pg_class, pg_proc, etc.).
        objid: PostgreSQL object ID within its class.
        objsubid: PostgreSQL sub-object ID (e.g., column number).
        objtype: Type of object (table, view, function, etc.).
        objnames: Object name components (schema, name, etc.).
        objargs: Object argument types for procedures/functions.
        description: Textual description of the object.
    """

    id: int = -1
    classid: int
    objid: int
    objsubid: int
    objtype: str
    objnames: list[str]
    objargs: list[str]
    description: str


class Column(BaseModel):
    """Model representing a database column.

    This class represents a column in a database table or view, including its
    data type, constraints, and description.

    Attributes:
        classid: PostgreSQL object class ID for the parent table/view.
        objid: PostgreSQL object ID of the parent table/view.
        objsubid: PostgreSQL sub-object ID (column number).
        name: Column name.
        type: PostgreSQL data type of the column.
        is_not_null: Boolean indicating if the column has a NOT NULL constraint.
        default_value: Default value expression for the column (if any).
        description: Object description containing metadata and textual description.
    """

    classid: int
    objid: int
    objsubid: int
    name: str
    type: str
    is_not_null: bool
    default_value: str | None = None
    description: ObjectDescription | None = None


class Dimension(BaseModel):
    """Model representing a dimension in a TimescaleDB hypertable.

    This class represents a partitioning dimension in a TimescaleDB hypertable,
    which can be time-based or space-based.

    Attributes:
        column_name: Name of the column used for partitioning.
        dimension_builder: Type of partitioning strategy (by_range, by_hash).
        partition_func: Custom partitioning function (if any).
        partition_interval: Time interval for time-based partitioning.
        number_partitions: Number of partitions for hash partitioning.
    """

    column_name: str
    dimension_builder: str
    partition_func: str | None = None
    partition_interval: str | None = None
    number_partitions: int | None = None


class View(BaseModel):
    """Model representing a database view.

    This class represents a view in a database, which can be a regular view,
    materialized view, or a TimescaleDB continuous aggregate view.

    Attributes:
        id: Semantic catalog ID (default: -1 if not assigned).
        classid: PostgreSQL object class ID.
        objid: PostgreSQL object ID.
        schema_name: Schema name where the view is defined.
        view_name: Name of the view.
        is_materialized: Boolean indicating if the view is materialized.
        is_continuous_aggregate: Boolean indicating if the view is a TimescaleDB continuous aggregate.
        columns: List of columns in the view.
        definition: SQL definition of the view.
        description: Object description containing metadata and textual description.
        sample: Sample data from the view (if available).
    """  # noqa: E501

    id: int = -1
    classid: int
    objid: int
    schema_name: str
    view_name: str
    is_materialized: bool
    is_continuous_aggregate: bool
    columns: list[Column] | None = None
    definition: str
    description: ObjectDescription | None = None
    sample: str | None = None


class Procedure(BaseModel):
    """Model representing a database procedure, function, or aggregate.

    This class represents a callable database object, which can be a procedure,
    function, or aggregate function.

    Attributes:
        id: Semantic catalog ID (default: -1 if not assigned).
        classid: PostgreSQL object class ID.
        objid: PostgreSQL object ID.
        schema_name: Schema name where the procedure is defined.
        proc_name: Name of the procedure.
        kind: Type of procedure ("procedure", "function", or "aggregate").
        identity_args: String representation of the argument types for identification.
        definition: SQL definition of the procedure.
        objargs: List of argument types as strings.
        description: Object description containing metadata and textual description.
    """

    id: int = -1
    classid: int
    objid: int
    schema_name: str
    proc_name: str
    kind: Literal["procedure", "function", "aggregate"]
    identity_args: str
    definition: str
    objargs: list[str] = []
    description: ObjectDescription | None = None


class Constraint(BaseModel):
    """Model representing a database constraint.

    This class represents a constraint in a database table, such as primary key,
    foreign key, unique, or check constraints.

    Attributes:
        name: Name of the constraint.
        definition: SQL definition of the constraint.
    """

    name: str
    definition: str


class Index(BaseModel):
    """Model representing a database index.

    This class represents an index on a database table.

    Attributes:
        name: Name of the index.
        definition: SQL definition of the index.
    """

    name: str
    definition: str


class Table(BaseModel):
    """Model representing a database table.

    This class represents a table in a database, including its columns, constraints,
    indexes, and potentially TimescaleDB hypertable dimensions.

    Attributes:
        id: Semantic catalog ID (default: -1 if not assigned).
        classid: PostgreSQL object class ID.
        objid: PostgreSQL object ID.
        schema_name: Schema name where the table is defined.
        table_name: Name of the table.
        persistence: Table persistence type ("temporary" or "unlogged") if applicable.
        columns: List of columns in the table.
        constraints: List of constraints on the table.
        indexes: List of indexes on the table.
        dimensions: List of TimescaleDB dimensions if the table is a hypertable.
        description: Object description containing metadata and textual description.
        sample: Sample data from the table (if available).
    """

    id: int = -1
    classid: int
    objid: int
    schema_name: str
    table_name: str
    persistence: Literal["temporary", "unlogged"] | None = None
    columns: list[Column] | None = None
    constraints: list[Constraint] | None = None
    indexes: list[Index] | None = None
    dimensions: list[Dimension] | None = None
    description: ObjectDescription | None = None
    sample: str | None = None


class SQLExample(BaseModel):
    """Model representing an example SQL query.

    This class represents an example SQL query with a description of what it does.
    These examples can be used to help users understand how to query the database.

    Attributes:
        id: Semantic catalog ID (default: -1 if not assigned).
        sql: The SQL query text.
        description: Description of what the SQL query does.
    """

    id: int = -1
    sql: str
    description: str


class Fact(BaseModel):
    """Model representing a fact about the database or domain.

    This class represents a descriptive fact about the database, its schema,
    or the business domain it models. These facts can provide context and information
    that isn't captured in the specific database object descriptions.

    Attributes:
        id: Semantic catalog ID (default: -1 if not assigned).
        description: The text of the fact.
    """

    id: int = -1
    description: str
