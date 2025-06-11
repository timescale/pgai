# ruff: noqa: E402

import sys
from importlib.util import find_spec

tiktoken = find_spec("tiktoken")
if tiktoken is None:
    print(
        "vectorizer-worker extra is not installed, please install it with `pip install pgai[vectorizer-worker]`",  # noqa: E501
        file=sys.stderr,
    )
    sys.exit(1)

from .create_vectorizer import CreateVectorizer
from .vectorizer import Executor, Vectorizer
from .worker import Worker

__all__ = [
    "Vectorizer",
    "Executor",
    "CreateVectorizer",
    "Worker",
]
