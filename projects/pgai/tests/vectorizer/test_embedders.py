import os

from dotenv import load_dotenv

from pgai.vectorizer.embedders import OpenAI


async def test_openai_embeddings():
    load_dotenv()
    client = OpenAI(
        implementation="openai",
        model="text-embedding-3-small",
        api_key_name="OPENAI_API_KEY",
    )
    client.set_api_key({"OPENAI_API_KEY": os.getenv("OPENAI_API_KEY")})
    result = client.embed(
        ["a"] * 800  # 800 chunks each 1 token
    )
    assert (
        len([value async for value in result][0]) == 800
    )  # One request with 800 embedding vectors


async def test_openai_embeddings_breaks_300k_tokens_but_fits_estimator():
    load_dotenv()
    client = OpenAI(
        implementation="openai",
        model="text-embedding-3-small",
        api_key_name="OPENAI_API_KEY",
    )
    client.set_api_key({"OPENAI_API_KEY": os.getenv("OPENAI_API_KEY")})
    result = client.embed(
        ["ф" * 300] * 1001  # 1001 chunks each 300 token = 300300 tokens
    )
    # Estimator counts utf-8 bytes as 0.25 tokens
    # which in this case is just 150150 tokens so input goes through one request
    responses = [response async for response in result]
    assert len(responses) == 1
    assert len(responses[0]) == 1001  # One request with 1001 embedding vectors


async def test_openai_embeddings_breaks_300k_tokens_and_also_estimator():
    load_dotenv()
    client = OpenAI(
        implementation="openai",
        model="text-embedding-3-small",
        api_key_name="OPENAI_API_KEY",
    )
    client.set_api_key({"OPENAI_API_KEY": os.getenv("OPENAI_API_KEY")})
    result = client.embed(
        ["中" * 1000] * 500  # 500 chunks each 1000 token = 500000 tokens
    )
    # Estimator counts utf-8 bytes as 0.25 tokens
    # zhong is 3 bytes = 0.75 tokens * 1000 * 500 = 375000 tokens
    # which should mean 2 requests
    responses = [response async for response in result]
    assert len(responses) == 2


async def test_openai_embeddings_doesnt_break_300k_tokens_but_estimator():
    load_dotenv()
    client = OpenAI(
        implementation="openai",
        model="text-embedding-3-small",
        api_key_name="OPENAI_API_KEY",
    )
    client.set_api_key({"OPENAI_API_KEY": os.getenv("OPENAI_API_KEY")})
    result = client.embed(
        ["apple " * 1000] * 299  # 299 chunks each 1001 token = 299299 tokens
    )
    # Estimator counts utf-8 bytes as 0.25 tokens
    # "apple " is 6 bytes = 1.5 tokens * 1000 * 299 = 448500 tokens
    # which should mean 2 requests
    responses = [response async for response in result]
    assert len(responses) == 2
