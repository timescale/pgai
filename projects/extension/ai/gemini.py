import os
from typing import Optional
import google.generativeai as genai
from google.generativeai import GenerativeModel as Gemini

DEFAULT_KEY_NAME = "GEMINI_API_KEY"


def make_client(
    api_key: str,
    base_url: Optional[str] = None,
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
) -> Gemini:
    args = {}
    if timeout is not None:
        args["timeout"] = timeout
    if max_retries is not None:
        args["max_retries"] = max_retries
    genai.configure(api_key=api_key)
    return Gemini(**args)
