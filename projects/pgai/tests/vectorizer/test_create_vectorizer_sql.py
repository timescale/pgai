# ruff: noqa: E501
from datetime import timedelta

from pgai.vectorizer import CreateVectorizer
from pgai.vectorizer.configuration import (
    ChunkingCharacterTextSplitterConfig,
    DestinationTableConfig,
    EmbeddingOpenaiConfig,
    IndexingHnswConfig,
    LoadingColumnConfig,
    ProcessingDefaultConfig,
    SchedulingTimescaledbConfig,
)


def test_basic_vectorizer_configuration():
    config = CreateVectorizer(
        source="public.documents",
        embedding=EmbeddingOpenaiConfig(
            model="text-embedding-ada-002",
            dimensions=1536,
            api_key_name="openai_api_key",
        ),
        destination=DestinationTableConfig(
            target_schema="vectorizer",
            target_table="document_embeddings",
        ),
    )

    expected_sql = """SELECTai.create_vectorizer(
     'public.documents'::regclass
     ,destination=>ai.destination_table(target_schema=>'vectorizer', target_table=>'document_embeddings')
     ,embedding=>ai.embedding_openai(model=>'text-embedding-ada-002', dimensions=>'1536', api_key_name=>'openai_api_key')
    )"""

    assert config.to_sql().replace(" ", "") == expected_sql.replace(" ", "")


def test_complex_vectorizer_configuration():
    config = CreateVectorizer(
        source="public.large_documents",
        loading=LoadingColumnConfig(column_name="content"),
        embedding=EmbeddingOpenaiConfig(
            model="text-embedding-ada-002", dimensions=1536
        ),
        chunking=ChunkingCharacterTextSplitterConfig(
            chunk_size=1000, chunk_overlap=100
        ),
        indexing=IndexingHnswConfig(m=16, ef_construction=100, opclass="vector_l2_ops"),
        processing=ProcessingDefaultConfig(batch_size=100, concurrency=4),
        scheduling=SchedulingTimescaledbConfig(schedule_interval=timedelta(hours=1)),
        enqueue_existing=True,
        destination=DestinationTableConfig(
            target_schema="vectors",
            target_table="chunked_embeddings",
        ),
    )

    expected_sql = """SELECT ai.create_vectorizer(
    'public.large_documents'::regclass
    ,destination=>ai.destination_table(target_schema=>'vectors',target_table=>'chunked_embeddings')
    ,loading=>ai.loading_column(column_name=>'content')
    ,embedding=>ai.embedding_openai(model=>'text-embedding-ada-002',dimensions=>'1536')
    ,chunking=>ai.chunking_character_text_splitter(chunk_size=>'1000',chunk_overlap=>'100')
    ,indexing=>ai.indexing_hnsw(opclass=>'vector_l2_ops',m=>'16',ef_construction=>'100')
    ,scheduling=>ai.scheduling_timescaledb(schedule_interval=>'3600seconds')
    ,processing=>ai.processing_default(batch_size=>'100',concurrency=>'4')
    ,enqueue_existing=>true
     )"""

    assert config.to_sql().replace(" ", "") == expected_sql.replace(" ", "")


def test_minimal_vectorizer_configuration():
    config = CreateVectorizer(source="public.simple_docs")

    expected_sql = """SELECT ai.create_vectorizer(\n'public.simple_docs'::regclass\n)"""

    assert config.to_sql().replace(" ", "") == expected_sql.replace(" ", "")
