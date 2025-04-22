alter table ai.vectorizer add column name name check (name ~ '^[a-z][a-z_0-9]*$');

do language plpgsql $block$
declare
    _vectorizer RECORD;
    _destination_type text;
    _target_schema text;
    _target_table text;
    _embedding_column text;
    _config jsonb;
    _name text;
    _destination_config jsonb;
begin
    -- Loop through all vectorizers
    for _vectorizer in select id, config from ai.vectorizer
    loop
        -- Extract the chunking config and chunk_column
        _config := _vectorizer.config;
        _destination_config := _config operator(pg_catalog.->) 'destination';
        _destination_type := _destination_config operator(pg_catalog.->>) 'implementation';
        if _destination_type = 'table' then
            _target_schema := _destination_config operator(pg_catalog.->>) 'target_schema';
            _target_table := _destination_config operator(pg_catalog.->>) 'target_table';
            _name := _target_schema operator(pg_catalog.||) '_' operator(pg_catalog.||) _target_table;
        elseif _destination_type = 'column' then
            _embedding_column := _destination_config operator(pg_catalog.->>) 'embedding_column';
            _name := _vectorizer.source_schema operator(pg_catalog.||) '_' operator(pg_catalog.||) _vectorizer.source_table operator(pg_catalog.||) '_' operator(pg_catalog.||) _embedding_column;
        end if;

        -- Update the vectorizer with new config
        update ai.vectorizer 
        set name = _name
        where id operator(pg_catalog.=) _vectorizer.id;
    end loop;
end;
$block$;

alter table ai.vectorizer alter column name set not null;
alter table ai.vectorizer add constraint vectorizer_name_unique unique (name);

drop function if exists ai.disable_vectorizer_schedule(int4);
drop function if exists ai.enable_vectorizer_schedule(int4);
drop function if exists ai.drop_vectorizer(int4, bool);
drop function if exists ai.vectorizer_queue_pending(int4, bool);
drop function if exists ai.vectorizer_embed(int4, text, text);