from typing import Literal

from pydantic import BaseModel


class View(BaseModel):
    id: int | None
    schema_name: str
    view_name: str
    is_materialized: bool
    definition: str


class Procedure(BaseModel):
    id: int | None
    schema_name: str
    proc_name: str
    kind: Literal["procedure", "function", "aggregate"]
    identity_args: str
    definition: str


class Column(BaseModel):
    num: int
    name: str
    type: str
    is_not_null: bool
    default_value: str | None = None


class Constraint(BaseModel):
    name: str
    definition: str


class Index(BaseModel):
    name: str
    definition: str


class Table(BaseModel):
    id: int | None
    schema_name: str
    table_name: str
    persistence: Literal["temporary", "unlogged"] | None = None
    columns: list[Column] | None = None
    constraints: list[Constraint] | None = None
    indexes: list[Index] | None = None
