do language plpgsql $block$
declare
    _rec pg_catalog.record;
    _sql pg_catalog.text;
begin
    -- loop through all vectorizers to extract queue tables information
    for _rec in (
        select queue_schema, queue_table from ai.vectorizer
    )
    loop

        select pg_catalog.format
               ( $sql$alter table %I.%I
                 add column if not exists loading_retries pg_catalog.int4 not null default 0
                 , add column if not exists loading_retry_after pg_catalog.timestamptz default null$sql$
                 , _rec.queue_schema
                 , _rec.queue_table
               ) into strict _sql;

        raise debug '%', _sql;
        execute _sql;
    end loop;
end;
$block$;
