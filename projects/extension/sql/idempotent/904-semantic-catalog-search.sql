--FEATURE-FLAG: text_to_sql

-------------------------------------------------------------------------------
-- _semantic_catalog_embed
create or replace function ai._semantic_catalog_embed
( catalog_id pg_catalog.int4
, prompt pg_catalog.text
) returns @extschema:vector@.vector
as $func$
declare
    _vectorizer_id pg_catalog.int4;
    _config pg_catalog.jsonb;
    _emb @extschema:vector@.vector;
begin
    select x.obj_vectorizer_id -- TODO: assumes the embedding settings are the same for obj and sql
    into strict _vectorizer_id
    from ai.semantic_catalog x
    where x.id operator(pg_catalog.=) catalog_id
    ;

    select v.config operator(pg_catalog.->) 'embedding'
    into strict _config
    from ai.vectorizer v
    where v.id operator(pg_catalog.=) _vectorizer_id
    ;

    case _config operator(pg_catalog.->>) 'implementation'
        when 'openai' then
            _emb = ai.openai_embed
            ( _config operator(pg_catalog.->>) 'model'
            , prompt
            , api_key_name=>(_config operator(pg_catalog.->>) 'api_key_name')
            , dimensions=>(_config operator(pg_catalog.->>) 'dimensions')::pg_catalog.int4
            , openai_user=>(_config operator(pg_catalog.->>) 'user')
            );
        when 'ollama' then
            _emb = ai.ollama_embed
            ( _config operator(pg_catalog.->>) 'model'
            , prompt
            , host=>(_config operator(pg_catalog.->>) 'base_url')
            , keep_alive=>(_config operator(pg_catalog.->>) 'keep_alive')
            , embedding_options=>(_config operator(pg_catalog.->) 'options')
            -- TODO: ai.ollama_embed doesn't have a dimensions parameter???
            );
        when 'voyageai' then
            _emb = ai.voyageai_embed
            ( _config operator(pg_catalog.->>) 'model'
            , prompt
            , input_type=>'query'
            , api_key_name=>(_config operator(pg_catalog.->>) 'api_key_name')
            -- TODO: ai.voyageai_embed doesn't have a dimensions parameter
            );
        else
            raise exception 'unsupported embedding implementation';
    end case;

    return _emb;
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- find_relevant_sql
create or replace function ai.find_relevant_sql
( prompt pg_catalog.text
, catalog_name pg_catalog.name default 'default'
, "limit" pg_catalog.int8 default 5
) returns table
( id pg_catalog.int4
, sql pg_catalog.text
, description pg_catalog.text
)
as $func$
declare
    _catalog_id pg_catalog.int4;
    _emb @extschema:vector@.vector;
    _sql pg_catalog.text;
begin
    select x.id into strict _catalog_id
    from ai.semantic_catalog x
    where x."name" operator(pg_catalog.=) catalog_name
    ;

    _emb = ai._semantic_catalog_embed(_catalog_id, prompt);

    _sql = pg_catalog.format
    ( $sql$
    select distinct x.id, x.sql, x.description
    from
    (
        select
          x.id
        , x.sql
        , x.description
        , x.embedding operator(@extschema:vector@.<=>) ($1::@extschema:vector@.vector(%s)) as dist
        from ai.semantic_catalog_sql_%s x
        order by dist
        limit %L
    ) x
    $sql$
    , @extschema:vector@.vector_dims(_emb)
    , _catalog_id
    , "limit"
    );

    return query execute _sql using _emb;
end;
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;
