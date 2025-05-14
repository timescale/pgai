import os

import pytest
from dotenv import load_dotenv

from pgai.vectorizer.embedders import OpenAI
from pgai.vectorizer.embeddings import (
    batch_indices,
)

token_documents = [5, 1, 1, 1, 1, 1, 1, 1, 1]
string_documents = [1, 8, 2, 5, 9, 5, 6, 11]


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
    input: list[int],
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


@pytest.fixture
def openai_client() -> OpenAI:
    """Create an OpenAI client."""
    load_dotenv()
    client = OpenAI(
        implementation="openai",
        model="text-embedding-3-small",
        api_key_name="OPENAI_API_KEY",  # type: ignore
    )
    client.set_api_key({"OPENAI_API_KEY": os.getenv("OPENAI_API_KEY")})
    return client


async def test_openai_embeddings(openai_client: OpenAI):
    result = openai_client.embed(
        ["a"] * 800  # 800 chunks each 1 token
    )
    assert (
        len([value async for value in result][0]) == 800
    )  # One request with 800 embedding vectors


async def test_openai_embeddings_breaks_300k_tokens_but_fits_estimator(
    openai_client: OpenAI,
):
    result = openai_client.embed(
        ["ф" * 300] * 1001  # 1001 chunks each 300 token = 300300 tokens
    )
    # Estimator counts utf-8 bytes as 0.25 tokens
    # which in this case is just 150150 tokens so input goes through one request
    responses = [response async for response in result]
    assert len(responses) == 1
    assert len(responses[0]) == 1001  # One request with 1001 embedding vectors


async def test_openai_embeddings_breaks_300k_tokens_and_also_estimator(
    openai_client: OpenAI,
):
    result = openai_client.embed(
        ["中" * 1000] * 500  # 500 chunks each 1000 token = 500000 tokens
    )
    # Estimator counts utf-8 bytes as 0.25 tokens
    # zhong is 3 bytes = 0.75 tokens * 1000 * 500 = 375000 tokens
    # which should mean 2 requests
    responses = [response async for response in result]
    assert len(responses) == 2


async def test_openai_embeddings_doesnt_break_300k_tokens_but_estimator(
    openai_client: OpenAI,
):
    result = openai_client.embed(
        ["apple " * 1000] * 299  # 299 chunks each 1001 token = 299299 tokens
    )
    # Estimator counts utf-8 bytes as 0.25 tokens
    # "apple " is 6 bytes = 1.5 tokens * 1000 * 299 = 448500 tokens
    # which should mean 2 requests
    responses = [response async for response in result]
    assert len(responses) == 2
