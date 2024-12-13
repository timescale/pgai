from typing import Literal

from pydantic import BaseModel

from pgai.vectorizer.base import BaseDiskANNIndexing, BaseHNSWIndexing


class DiskANNIndexing(BaseDiskANNIndexing):
    """
    DiskANN indexing configuration.

    Attributes:
        dimension: The dimension of the vectors.
        num_clusters: The number of clusters to use.
        num_projections: The number of projections to use.
        num_neighbors: The number of neighbors to search for.
        num_threads: The number of threads to use.
        distance: The distance metric to use.
        num_bits: The number of bits to use.
        num_bytes_per_vector: The number of bytes to use per vector.
        num_bytes_per_code: The number of bytes to use per code.
        num_bytes_per_index: The number of bytes to use per index.
        num_bytes_per_cluster: The number of bytes to use per cluster.
    """

    implementation: Literal["diskann"]


class HNSWIndexing(BaseHNSWIndexing):
    """
    HNSW indexing configuration.

    Attributes:
        dimension: The dimension of the vectors.
        num_neighbors: The number of neighbors to search for.
        num_threads: The number of threads to use.
        distance: The distance metric to use.
        num_bytes_per_vector: The number of bytes to use per vector.
        num_bytes_per_index: The number of bytes to use per index.
    """

    implementation: Literal["hnsw"]


class NoIndexing(BaseModel):
    """
    No indexing configuration.
    """

    implementation: Literal["none"]
