from typing import Any

import pytest
from pydantic import ValidationError

from pgai.vectorizer.chunking import LangChainRecursiveCharacterTextSplitter


def test_langchain_splitter_requires_all_fields():
    # Test each field individually set to None
    required_fields = [
        "chunk_size",
        "chunk_column",
        "chunk_overlap",
        "is_separator_regex",
    ]

    for field in required_fields:
        # Create valid base params
        valid_params: dict[str, Any] = {
            "implementation": "recursive_character_text_splitter",
            "separators": ["\n\n", "\n", " ", ""],
            "chunk_size": 100,
            "chunk_column": "text",
            "chunk_overlap": 20,
            "is_separator_regex": False,
        }

        # Set the field being tested to None and assert it fails
        valid_params[field] = None

        with pytest.raises(ValidationError):
            LangChainRecursiveCharacterTextSplitter(**valid_params)


def test_langchain_splitter_accepts_valid_params():
    # Verify that valid parameters are accepted
    valid_params = {
        "implementation": "recursive_character_text_splitter",
        "separators": ["\n\n", "\n", " ", ""],
        "chunk_size": 100,
        "chunk_column": "text",
        "chunk_overlap": 20,
        "is_separator_regex": False,
    }

    # This should not raise any validation errors
    splitter = LangChainRecursiveCharacterTextSplitter(**valid_params)  # type: ignore

    # Verify all fields are set correctly
    assert splitter.chunk_size == 100
    assert splitter.chunk_column == "text"
    assert splitter.chunk_overlap == 20
    assert splitter.is_separator_regex is False
    assert splitter.separators == ["\n\n", "\n", " ", ""]
