
import os
from typing import Union


def asbool(value: Union[str, None]):
    """Convert the given String to a boolean object.

    Accepted values are `True` and `1`.
    """    
    if value is None:
        return False

    return value.lower() in ("true", "1")

def get_bool_env(name) -> bool:
    if name is None:
        return False

    return asbool(os.getenv(name))