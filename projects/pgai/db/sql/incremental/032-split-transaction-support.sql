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
end;
$block$;
