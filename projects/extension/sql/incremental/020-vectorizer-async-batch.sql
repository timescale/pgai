ALTER TABLE ai.vectorizer
    ADD COLUMN IF NOT EXISTS async_batch_queue_table pg_catalog.name DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS async_batch_chunks_table pg_catalog.name DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS async_batch_polling_interval interval DEFAULT interval '5 minutes';
