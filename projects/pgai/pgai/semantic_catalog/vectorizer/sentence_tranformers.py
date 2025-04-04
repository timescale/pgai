from collections.abc import Sequence

import numpy as np
import numpy.typing as npt
from sentence_transformers import SentenceTransformer

from pgai.semantic_catalog.vectorizer import EmbedRow, SentenceTransformersConfig


async def embed_batch(
    config: SentenceTransformersConfig, batch: list[EmbedRow]
) -> None:
    st = SentenceTransformer(
        config.model, trust_remote_code=True
    )  # TODO: configurable?
    sentences: list[str] = [x.content for x in batch]
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
