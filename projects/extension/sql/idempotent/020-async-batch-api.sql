-------------------------------------------------------------------------------
-- _vectorizer_create_async_batch__table
create or replace function ai._vectorizer_create_async_batch_tables(
  schema_name name,
  async_batch_queue_table name,
  async_batch_chunks_table name,
  source_pk pg_catalog.jsonb,
  grant_to name []
) returns void as
$func$
declare
  _sql text;
  _index_name text;
  _pk_cols pg_catalog.text;
begin
    -- create the batches table
    select pg_catalog.format
           ( $sql$create table %I.%I(
                    id VARCHAR(255)    PRIMARY KEY,
                    created_at         TIMESTAMP(0) NOT NULL DEFAULT NOW(),
                    status             TEXT NOT NULL,
                    errors             JSONB,
                    metadata           JSONB,
                    next_attempt_after TIMESTAMPTZ NOT NULL,
                    total_attempts INT NOT NULL DEFAULT 0
                )$sql$
            , schema_name
            , async_batch_queue_table
           ) into strict _sql
    ;
    execute _sql;

    select pg_catalog.format
           ( $sql$create index on %I.%I (status)$sql$
               , schema_name
               , async_batch_queue_table
           ) into strict _sql
    ;
    execute _sql;

    select pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' order by x.pknum)
    into strict _pk_cols
    from pg_catalog.jsonb_to_recordset(source_pk) x(pknum int, attname name)
    ;

    -- create the batch chunks table. The chunk content needs to be stored
    -- because when retrieving the batches, we need to map each embedding to
    -- the chunk so that we can save them in the embeddings store table.
    select pg_catalog.format(
      $sql$
        create table %I.%I(
        %s,
        chunk_seq int not null,
        created_at timestamptz not null default now(),
        async_batch_id text not null references %I.%I (id) on delete cascade,
        chunk text not null,
        unique (%s, chunk_seq)
      )$sql$,
      schema_name,
      async_batch_chunks_table,
      (
        select pg_catalog.string_agg(
          pg_catalog.format('%I %s not null' , x.attname , x.typname),
          ', '
          order by x.attnum
        )
        from pg_catalog.jsonb_to_recordset(source_pk) x(attnum int, attname name, typname name)
      ),
      schema_name,
      async_batch_queue_table,
      _pk_cols
    ) into strict _sql
    ;
    execute _sql;

    if grant_to is not null then
      -- grant select, update, delete on batches table to grant_to roles
      select pg_catalog.format(
        $sql$grant select, insert, update, delete on %I.%I to %s$sql$,
        schema_name,
        async_batch_queue_table,
        (
          select pg_catalog.string_agg(pg_catalog.quote_ident(x), ', ')
          from pg_catalog.unnest(grant_to) x
        )
      ) into strict _sql;
      execute _sql;

      -- grant select, update, delete on batch chunks table to grant_to roles
      select pg_catalog.format(
        $sql$grant select, insert, update, delete on %I.%I to %s$sql$,
        schema_name,
        async_batch_chunks_table,
        (
          select pg_catalog.string_agg(pg_catalog.quote_ident(x), ', ')
          from pg_catalog.unnest(grant_to) x
        )
      ) into strict _sql;
      execute _sql;
    end if;
end;
$func$
language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp;

-------------------------------------------------------------------------------
-- vectorizer_enable_async_batches
create or replace function ai.vectorizer_enable_async_batches(
    vectorizer_id pg_catalog.int4
) returns void
as $func$
declare
    _config pg_catalog.jsonb;
begin
    select config into _config
    from ai.vectorizers
    where id = vectorizer_id;

    if _config is null then
        raise exception 'vectorizer with id % not found', vectorizer_id;
    end if;

    if not _config ? 'use_async_batch_api' then
        raise exception 'vectorizer configuration does not support async batch api';
    end if;

    update ai.vectorizers
    set config = jsonb_set(config, '{async_batch_enabled}', 'true'::jsonb)
    where id = vectorizer_id;

    perform
end
$func$ language plpgsql security definer
set search_path to pg_catalog, pg_temp;

-------------------------------------------------------------------------------
-- vectorizer_disable_async_batches
create or replace function ai.vectorizer_disable_async_batches(
    vectorizer_id pg_catalog.int4
) returns void
as $func$
declare
    _config pg_catalog.jsonb;
begin
    select config into _config
    from ai.vectorizers
    where id = vectorizer_id;

    if _config is null then
        raise exception 'vectorizer with id % not found', vectorizer_id;
    end if;

    if not _config ? 'use_async_batch_api' then
        raise exception 'vectorizer configuration does not support async batch api';
    end if;

    update ai.vectorizers
    set config = jsonb_set(config, '{async_batch_enabled}', 'false'::jsonb)
    where id = vectorizer_id;

    perform
end
$func$ language plpgsql security definer
set search_path to pg_catalog, pg_temp;
