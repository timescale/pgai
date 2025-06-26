-- rename loading_retries and loading_retry_after for all existing queue tables
do language plpgsql $block$
declare
    _vectorizer record;
begin
    for _vectorizer in select queue_schema, queue_table from ai.vectorizer
    loop
        execute format('alter table %I.%I rename column loading_retries to attempts', _vectorizer.queue_schema, _vectorizer.queue_table);
        execute format('alter table %I.%I rename column loading_retry_after to retry_after', _vectorizer.queue_schema, _vectorizer.queue_table);
    end loop;
    for _vectorizer in select queue_schema, queue_failed_table from ai.vectorizer
    loop
        execute format('alter table %I.%I add column attempts pg_catalog.int4 not null default 0', _vectorizer.queue_schema, _vectorizer.queue_failed_table);
    end loop;
end;
$block$;
