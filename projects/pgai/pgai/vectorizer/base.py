from types import UnionType
from typing import Annotated, Any, Literal, TypeVar, Union, get_args, get_origin

from annotated_types import Gt, Le
from openai import BaseModel
from pydantic.fields import FieldInfo


class BaseOpenAIConfig(BaseModel):
    model: str
    dimensions: int | None = None


class BaseOllamaConfig(BaseModel):
    model: str
    dimensions: int
    base_url: str | None = None
    keep_alive: str | None = None  # this is only `str` because of the SQL API


class BaseVoyageAIConfig(BaseModel):
    model: str
    dimensions: int
    input_type: Literal["document"] | Literal["query"] | None = None


class ChunkingCharacterTextSplitter(BaseModel):
    chunk_column: str
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    separator: str | None = None
    is_separator_regex: bool | None = None


class ChunkingRecursiveCharacterTextSplitter(BaseModel):
    chunk_column: str
    separators: list[str] | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    is_separator_regex: bool | None = None


class BasePythonTemplate(BaseModel):
    template: str


class BaseProcessing(BaseModel):
    batch_size: Annotated[int, Gt(gt=0), Le(le=2048)] = 50
    concurrency: Annotated[int, Gt(gt=0), Le(le=10)] = 1


T = TypeVar("T", bound=BaseModel)


def required(cls: type[T]) -> type[T]:
    """Decorator function used to modify a pydantic model's fields to be required.
    This allows us to only specify fields in one place, leave them optional
    for user input in alembic migrations. But require them when parsing the
    stored database configurations.

    Returns:
        A decorator function that modifies the model class

    Example:
        @required
        class Child(Parent):
            pass
    """

    def remove_none_from_annotation(
        annotation: type[Any] | UnionType | None,
    ) -> type[Any] | UnionType | None:
        if isinstance(annotation, UnionType) or get_origin(annotation) is Union:
            args = get_args(annotation)
            non_none_args = tuple(arg for arg in args if arg is not type(None))
            if len(non_none_args) == 1:
                return non_none_args[0]
            return Union[non_none_args]  # noqa: UP007
        return annotation

    def dec(_cls: type[T]) -> type[T]:
        new_fields = {}
        for name, field in _cls.model_fields.items():
            if not field.is_required():
                # Create new required field with None removed from annotation
                new_annotation = remove_none_from_annotation(field.annotation)
                new_field = FieldInfo.from_annotated_attribute(
                    new_annotation,  # type: ignore
                    ...,  # Using ... as default makes it required
                )
                new_fields[name] = new_field
            else:
                new_fields[name] = field
        _cls.model_fields = new_fields
        return _cls

    return dec(cls)
