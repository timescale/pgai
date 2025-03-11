-------------------------------------------------------------------------------
-- execute_vectorizer
create or replace function ai.execute_vectorizer(vectorizer_id pg_catalog.int4) returns void
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.vectorizer
    ai.vectorizer.execute_vectorizer(plpy, vectorizer_id)
$python$
language plpython3u volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- vectorizer_embed
create or replace function ai.vectorizer_embed
( embedding_config pg_catalog.jsonb
, input_text pg_catalog.text
, input_type pg_catalog.text default null
) returns @extschema:vector@.vector
as $func$
declare
_emb @extschema:vector@.vector;
begin
case embedding_config operator(pg_catalog.->>) 'implementation'
        when 'openai' then
            _emb = ai.openai_embed
            ( embedding_config operator(pg_catalog.->>) 'model'
            , input_text
            , api_key_name=>(embedding_config operator(pg_catalog.->>) 'api_key_name')
            , dimensions=>(embedding_config operator(pg_catalog.->>) 'dimensions')::pg_catalog.int4
            , openai_user=>(embedding_config operator(pg_catalog.->>) 'user')
            );
when 'ollama' then
            _emb = ai.ollama_embed
            ( embedding_config operator(pg_catalog.->>) 'model'
            , input_text
            , host=>(embedding_config operator(pg_catalog.->>) 'base_url')
            , keep_alive=>(embedding_config operator(pg_catalog.->>) 'keep_alive')
            , embedding_options=>(embedding_config operator(pg_catalog.->) 'options')
            );
when 'voyageai' then
            _emb = ai.voyageai_embed
            ( embedding_config operator(pg_catalog.->>) 'model'
            , input_text
            , input_type=>coalesce(input_type, 'query')
            , api_key_name=>(embedding_config operator(pg_catalog.->>) 'api_key_name')
            );
else
            raise exception 'unsupported embedding implementation';
end case;

return _emb;
end
$func$ language plpgsql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- vectorizer_embed
create or replace function ai.vectorizer_embed
( vectorizer_id pg_catalog.int4
, input_text pg_catalog.text
, input_type pg_catalog.text default null
) returns @extschema:vector@.vector
as $func$
select ai.vectorizer_embed
       ( v.config operator(pg_catalog.->) 'embedding'
           , input_text
           , input_type
       )
from ai.vectorizer v
where v.id operator(pg_catalog.=) vectorizer_id
;
$func$ language sql stable security invoker
set search_path to pg_catalog, pg_temp
;


-- TODO!
-------------------------------------------------------------------------------
-- _vectorizer_handle_drops
create or replace function ai._vectorizer_handle_drops()
returns event_trigger as
$func$
declare
_id int;
begin
    -- this function is security definer
    -- fully-qualify everything and be careful of security holes
for _id in
    (
        select distinct v.id
        from pg_catalog.pg_event_trigger_dropped_objects() d
        inner join ai.vectorizer v
        on ((d.schema_name, d.object_name) in
            ( (v.source_schema, v.source_table)
            , (v.target_schema, v.target_table)
            , (v.queue_schema, v.queue_table)
            )
        )
        where pg_catalog.lower(d.object_type) operator(pg_catalog.=) 'table'
    )
    loop
        -- this may cause recursive invocations of this event trigger
        -- however it does not cause a problem
        raise notice 'associated table for vectorizer % dropped. dropping vectorizer', _id;
        perform ai.drop_vectorizer(_id);
end loop;
end;
$func$
language plpgsql volatile security definer -- definer on purpose!
set search_path to pg_catalog, pg_temp
;

-- install the event trigger if not exists
do language plpgsql $block$
begin
    -- if the event trigger already exists, noop
    perform
from pg_catalog.pg_event_trigger g
    where g.evtname operator(pg_catalog.=) '_vectorizer_handle_drops'
    and g.evtfoid operator(pg_catalog.=) pg_catalog.to_regproc('ai._vectorizer_handle_drops')
    ;
    if found then
        return;
end if;

    create event trigger _vectorizer_handle_drops
    on sql_drop
    execute function ai._vectorizer_handle_drops();
end
$block$;
