from typing import Literal

from pydantic import BaseModel


class DiskANNIndexing(BaseModel):
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
    min_rows: int
    storage_layout: Literal["memory_optimized", "plain"] | None = None
    num_neighbors: int | None = None
    search_list_size: int | None = None
    max_alpha: float | None = None
    num_dimensions: int | None = None
    num_bits_per_dimension: int | None = None
    create_when_queue_empty: bool


class HNSWIndexing(BaseModel):
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
    min_rows: int
    opclass: Literal["vector_cosine_ops", "vector_l1_ops", "vector_ip_ops"]
    m: int
    ef_construction: int
    create_when_queue_empty: bool


class NoIndexing(BaseModel):
    """
    No indexing configuration.
    """

    implementation: Literal["none"]
