from typing import Literal

from pydantic import BaseModel


class Column(BaseModel):
    classid: int
    objid: int
    objsubid: int
    name: str
    type: str
    is_not_null: bool
    default_value: str | None = None


class View(BaseModel):
    classid: int
    objid: int
    schema_name: str
    view_name: str
    is_materialized: bool
    columns: list[Column] | None = None
    definition: str


class Procedure(BaseModel):
    classid: int
    objid: int
    schema_name: str
    proc_name: str
    kind: Literal["procedure", "function", "aggregate"]
    identity_args: str
    definition: str
    objargs: list[str] = []


class Constraint(BaseModel):
    name: str
    definition: str


class Index(BaseModel):
    name: str
    definition: str


class Table(BaseModel):
    classid: int
    objid: int
    schema_name: str
    table_name: str
    persistence: Literal["temporary", "unlogged"] | None = None
    columns: list[Column] | None = None
    constraints: list[Constraint] | None = None
    indexes: list[Index] | None = None


class Description(BaseModel):
    classid: int
    objid: int
    objsubid: int
    objtype: str
    objnames: list[str]
    objargs: list[str]
    description: str
