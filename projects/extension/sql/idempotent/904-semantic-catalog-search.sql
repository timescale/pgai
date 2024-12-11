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
            );
        when 'voyageai' then
            _emb = ai.voyageai_embed
            ( _config operator(pg_catalog.->>) 'model'
            , prompt
            , input_type=>'query'
            , api_key_name=>(_config operator(pg_catalog.->>) 'api_key_name')
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
( catalog_id pg_catalog.int4
, embedding @extschema:vector@.vector
, "limit" pg_catalog.int8 default 5
) returns table
( id pg_catalog.int4
, sql pg_catalog.text
, description pg_catalog.text
)
as $func$
begin
    return query execute pg_catalog.format
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
    , @extschema:vector@.vector_dims(embedding)
    , catalog_id
    , "limit"
    ) using embedding;
end;
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
    _embedding @extschema:vector@.vector;
begin
    select x.id into strict _catalog_id
    from ai.semantic_catalog x
    where x."name" operator(pg_catalog.=) catalog_name
    ;

    _embedding = ai._semantic_catalog_embed(_catalog_id, prompt);

    return query
    select *
    from ai.find_relevant_sql
    ( _catalog_id
    , _embedding
    , "limit"
    );
end;
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- find_relevant_obj
create or replace function ai.find_relevant_obj
( catalog_id pg_catalog.int4
, embedding @extschema:vector@.vector
, "limit" pg_catalog.int8 default 5
) returns table
( objtype pg_catalog.text
, objnames pg_catalog.text[]
, objargs pg_catalog.text[]
, classid pg_catalog.oid
, objid pg_catalog.oid
, objsubid pg_catalog.int4
, description pg_catalog.text
)
as $func$
begin
    return query execute pg_catalog.format
    ( $sql$
    select distinct
      x.objtype
    , x.objnames
    , x.objargs
    , x.classid
    , x.objid
    , x.objsubid
    , x.description
    from
    (
        select
          x.objtype
        , x.objnames
        , x.objargs
        , x.classid
        , x.objid
        , x.objsubid
        , x.description
        , x.embedding operator(@extschema:vector@.<=>) ($1::@extschema:vector@.vector(%s)) as dist
        from ai.semantic_catalog_obj_%s x
        order by dist
        limit %L
    ) x
    $sql$
    , @extschema:vector@.vector_dims(embedding)
    , catalog_id
    , "limit"
    ) using embedding;
end;
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- find_relevant_obj
create or replace function ai.find_relevant_obj
( prompt pg_catalog.text
, catalog_name pg_catalog.name default 'default'
, "limit" pg_catalog.int8 default 5
) returns table
( objtype pg_catalog.text
, objnames pg_catalog.text[]
, objargs pg_catalog.text[]
, classid pg_catalog.oid
, objid pg_catalog.oid
, objsubid pg_catalog.int4
, description pg_catalog.text
)
as $func$
declare
    _catalog_id pg_catalog.int4;
    _embedding @extschema:vector@.vector;
begin
    select x.id into strict _catalog_id
    from ai.semantic_catalog x
    where x."name" operator(pg_catalog.=) catalog_name
    ;

    _embedding = ai._semantic_catalog_embed(_catalog_id, prompt);

    return query
    select *
    from ai.find_relevant_obj
    ( _catalog_id
    , _embedding
    , "limit"
    );
end;
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;
