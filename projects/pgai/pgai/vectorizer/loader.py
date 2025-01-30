from typing import Literal

from pydantic import BaseModel


class pgaiFileLoader(BaseModel):
    implementation: Literal["file_loader"]
    url_column: str
