-------------------------------------------------------------------------------
-- _vectorizer_create_queue_table
create or replace function ai._vectorizer_create_embedding_batches_table
( embedding_batch_schema name
, embedding_batch_table name
, embedding_batch_chunks_table name
, grant_to name[]
) returns void as
$func$
declare
    _sql text;
begin
    -- create the batches table
    select pg_catalog.format
           ( $sql$create table %I.%I(
    openai_batch_id VARCHAR(255) PRIMARY KEY,
    input_file_id   VARCHAR(255) NOT NULL,
    output_file_id  VARCHAR(255),
    status          VARCHAR(255) NOT NULL,
    errors          JSONB,
    created_at      TIMESTAMP(0) NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMP(0),
    completed_at    TIMESTAMP(0),
    failed_at       TIMESTAMP(0),
    next_attempt_after TIMESTAMPTZ,
    total_attempts BIGINT NOT NULL DEFAULT 0
))$sql$
               , embedding_batch_schema
               , embedding_batch_table
           ) into strict _sql
    ;
    execute _sql;

    -- create the index
    select pg_catalog.format
           ( $sql$create index on %I.%I (status)$sql$
               , embedding_batch_schema, embedding_batch_table
           ) into strict _sql
    ;
    execute _sql;

    -- create the batch chunks table
    select pg_catalog.format
           ( $sql$create table %I.%I(
    id                 VARCHAR(255) PRIMARY KEY,
    embedding_batch_id VARCHAR(255) REFERENCES %I.%I (openai_batch_id),
    chunk              TEXT
))$sql$
               , embedding_batch_schema
               , embedding_batch_chunks_table
               , embedding_batch_schema
               , embedding_batch_table
           ) into strict _sql
    ;
    execute _sql;

    if grant_to is not null then
        -- grant usage on queue schema to grant_to roles
        select pg_catalog.format
               ( $sql$grant usage on schema %I to %s$sql$
                   , embedding_batch_schema
                   , (
                     select pg_catalog.string_agg(pg_catalog.quote_ident(x), ', ')
                     from pg_catalog.unnest(grant_to) x
                 )
               ) into strict _sql;
        execute _sql;

        -- grant select, update, delete on batches table to grant_to roles
        select pg_catalog.format
               ( $sql$grant select, insert, update, delete on %I.%I to %s$sql$
                   , embedding_batch_schema
                   , embedding_batch_table
                   , (
                     select pg_catalog.string_agg(pg_catalog.quote_ident(x), ', ')
                     from pg_catalog.unnest(grant_to) x
                 )
               ) into strict _sql;
        execute _sql;

        -- grant select, update, delete on batch chunks table to grant_to roles
        select pg_catalog.format
               ( $sql$grant select, insert, update, delete on %I.%I to %s$sql$
                   , embedding_batch_schema
                   , embedding_batch_chunks_table
                   , (
                     select pg_catalog.string_agg(pg_catalog.quote_ident(x), ', ')
                     from pg_catalog.unnest(grant_to) x
                 )
               ) into strict _sql;
        execute _sql;
    end if;
end;
$func$
    language plpgsql volatile security invoker
                     set search_path to pg_catalog, pg_temp
;

