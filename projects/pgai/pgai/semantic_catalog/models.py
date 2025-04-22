from typing import Literal

from pydantic import BaseModel


class ObjectDescription(BaseModel):
    id: int = -1
    classid: int
    objid: int
    objsubid: int
    objtype: str
    objnames: list[str]
    objargs: list[str]
    description: str


class Column(BaseModel):
    classid: int
    objid: int
    objsubid: int
    name: str
    type: str
    is_not_null: bool
    default_value: str | None = None
    description: ObjectDescription | None = None


class View(BaseModel):
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
    name: str
    definition: str


class Index(BaseModel):
    name: str
    definition: str


class Table(BaseModel):
    id: int = -1
    classid: int
    objid: int
    schema_name: str
    table_name: str
    persistence: Literal["temporary", "unlogged"] | None = None
    columns: list[Column] | None = None
    constraints: list[Constraint] | None = None
    indexes: list[Index] | None = None
    description: ObjectDescription | None = None
    sample: str | None = None


class SQLExample(BaseModel):
    id: int = -1
    sql: str
    description: str


class Fact(BaseModel):
    id: int = -1
    description: str
