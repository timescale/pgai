from typing import Any

import pytest

from pgai.vectorizer.embeddings import batch_indices

token_documents = [[1, 2, 3, 4, 5], [2], [3], [4], [5], [6], [7], [8], [9]]
string_documents = [
    "A",
    "sequence",
    "of",
    "chunks",
    "which are",
    "split",
    "from a",
    "larger text",
]


@pytest.mark.parametrize(
    "input,batch_size,token_limit,expected,error",
    [
        (
            [],
            1,
            None,
            [],
            None,
        ),
        (
            token_documents,
            1,
            None,
            [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 9)],
            None,
        ),
        (
            token_documents,
            3,
            None,
            [(0, 3), (3, 6), (6, 9)],
            None,
        ),
        (
            token_documents,
            5,
            None,
            [(0, 5), (5, 9)],
            None,
        ),
        (
            token_documents,
            5,
            6,
            [(0, 2), (2, 7), (7, 9)],
            None,
        ),
        (
            token_documents,
            5,
            2,
            None,
            "chunk length 5 greater than max_tokens_per_batch 2",
        ),
        (
            string_documents,
            5,
            20,
            [(0, 4), (4, 7), (7, 8)],
            None,
        ),
    ],
)
def test_batch_indices(
    input: list[Any],
    batch_size: int,
    token_limit: int | None,
    expected: list[tuple[int, int]],
    error: str,
):
    try:
        indices = batch_indices(input, batch_size, token_limit)
        assert indices == expected
    except BaseException as e:
        assert str(e) == error
