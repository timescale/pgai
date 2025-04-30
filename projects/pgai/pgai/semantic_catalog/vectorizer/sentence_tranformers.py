import logging
from collections.abc import Sequence
from contextlib import contextmanager

import numpy as np
import numpy.typing as npt
from sentence_transformers import SentenceTransformer

from pgai.semantic_catalog.vectorizer import SentenceTransformersConfig
from pgai.semantic_catalog.vectorizer.models import EmbedRow


@contextmanager
def disable_logging():
    """
    Disable logging for the sentence_transformers and transformers_modules
    libraries.
    """
    st_logger = logging.getLogger("sentence_transformers")
    st_prev_level = st_logger.level
    st_logger.setLevel(logging.ERROR)
    t_logger = logging.getLogger("transformers_modules")
    t_prev_level = t_logger.level
    t_logger.setLevel(logging.ERROR)

    try:
        yield
    finally:
        st_logger.setLevel(st_prev_level)
        t_logger.setLevel(t_prev_level)


async def embed_batch(
    config: SentenceTransformersConfig, batch: list[EmbedRow]
) -> None:
    st = SentenceTransformer(
        config.model, trust_remote_code=True
    )  # TODO: configurable?
    sentences: list[str] = [x.content for x in batch]
    with disable_logging():
        results: npt.NDArray[np.float64] = st.encode(  # pyright: ignore [reportUnknownMemberType]
            sentences=sentences,
            prompt_name=None,
            prompt=None,
            batch_size=len(batch),
            show_progress_bar=False,
            output_value="sentence_embedding",
            precision="float32",
            convert_to_numpy=True,
            convert_to_tensor=False,
            device=None,
            normalize_embeddings=True,
        )
    assert len(results) == len(batch)
    for i, row in enumerate(results):
        batch[i].vector = list(row)


async def embed_query(
    config: SentenceTransformersConfig, query: str
) -> Sequence[float]:
    st = SentenceTransformer(
        config.model, trust_remote_code=True
    )  # TODO: configurable?
    sentences: list[str] = [query]
    with disable_logging():
        results: npt.NDArray[np.float64] = st.encode(  # pyright: ignore [reportUnknownMemberType]
            sentences=sentences,
            prompt_name=None,
            prompt=None,
            batch_size=1,
            show_progress_bar=False,
            output_value="sentence_embedding",
            precision="float32",
            convert_to_numpy=True,
            convert_to_tensor=False,
            device=None,
            normalize_embeddings=True,
        )
    assert len(results) == 1
    return list(results[0])
