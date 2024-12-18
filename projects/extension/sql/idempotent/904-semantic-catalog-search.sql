--FEATURE-FLAG: text_to_sql


-------------------------------------------------------------------------------
-- _semantic_catalog_embed
create or replace function ai._semantic_catalog_embed
( catalog_id pg_catalog.int4
, prompt pg_catalog.text
) returns @extschema:vector@.vector
as $func$
    select ai.vectorizer_embed
    ( v.config operator(pg_catalog.->) 'embedding'
    , prompt
    )
    from ai.semantic_catalog x
    inner join ai.vectorizer v
    on (x.obj_vectorizer_id operator(pg_catalog.=) v.id)
    where x.id operator(pg_catalog.=) catalog_id
    ;
$func$ language sql stable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- find_relevant_sql
create or replace function ai._find_relevant_sql
( catalog_id pg_catalog.int4
, embedding @extschema:vector@.vector
, "limit" pg_catalog.int8 default 5
, max_dist pg_catalog.float8 default null
) returns table
( id pg_catalog.int4
, sql pg_catalog.text
, description pg_catalog.text
, dist pg_catalog.float8
)
as $func$
declare
    _dimensions pg_catalog.int4;
    _sql pg_catalog.text;
begin
    _dimensions = @extschema:vector@.vector_dims(embedding);

    _sql = pg_catalog.format
    ( $sql$
    select x.id, x.sql, x.description, min(x.dist) as dist
    from
    (
        select
          x.id
        , x.sql
        , x.description
        , x.embedding operator(@extschema:vector@.<=>) ($1::@extschema:vector@.vector(%s)) as dist
        from ai.semantic_catalog_sql_%s x
        %s
        order by dist
        limit %L
    ) x
    group by x.id, x.sql, x.description
    order by min(x.dist)
    $sql$
    , _dimensions
    , catalog_id
    , case
        when max_dist is null then ''
        else pg_catalog.format
        ( $sql$where (x.embedding operator(@extschema:vector@.<=>) ($1::@extschema:vector@.vector(%s))) <= %s$sql$
        , _dimensions
        , max_dist
        )
      end
    , "limit"
    );
    -- raise log '%', _sql;

    return query execute _sql using embedding;
end;
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- find_relevant_sql
create or replace function ai.find_relevant_sql
( prompt pg_catalog.text
, "limit" pg_catalog.int8 default 5
, max_dist pg_catalog.float8 default null
, catalog_name pg_catalog.name default 'default'
) returns table
( id pg_catalog.int4
, sql pg_catalog.text
, description pg_catalog.text
, dist pg_catalog.float8
)
as $func$
declare
    _catalog_id pg_catalog.int4;
    _vectorizer_id pg_catalog.int4;
    _embedding @extschema:vector@.vector;
begin
    select
      x.id
    , x.obj_vectorizer_id
    into strict
      _catalog_id
    , _vectorizer_id
    from ai.semantic_catalog x
    where x.catalog_name operator(pg_catalog.=) find_relevant_sql.catalog_name
    ;

    _embedding = ai.vectorizer_embed(_vectorizer_id, prompt);

    return query
    select *
    from ai._find_relevant_sql
    ( _catalog_id
    , _embedding
    , "limit"
    , max_dist
    );
end;
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- find_relevant_obj
create or replace function ai._find_relevant_obj
( catalog_id pg_catalog.int4
, embedding @extschema:vector@.vector
, "limit" pg_catalog.int8 default 5
, objtypes pg_catalog.text[] default null
, max_dist pg_catalog.float8 default null
) returns table
( objtype pg_catalog.text
, objnames pg_catalog.text[]
, objargs pg_catalog.text[]
, classid pg_catalog.oid
, objid pg_catalog.oid
, objsubid pg_catalog.int4
, description pg_catalog.text
, dist pg_catalog.float8
)
as $func$
declare
    _dimensions pg_catalog.int4;
    _sql pg_catalog.text;
begin
    _dimensions = @extschema:vector@.vector_dims(embedding);

    _sql = pg_catalog.format
    ( $sql$
    select
      x.objtype
    , x.objnames
    , x.objargs
    , x.classid
    , x.objid
    , x.objsubid
    , x.description
    , min(x.dist) as dist
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
        where pg_catalog.has_schema_privilege($2, x.objnames[1], 'usage') and
        case x.objtype
            when 'table' then pg_catalog.has_table_privilege($2, x.objid, 'select')
            when 'view' then pg_catalog.has_table_privilege($2, x.objid, 'select')
            when 'table column' then pg_catalog.has_column_privilege($2, x.objid, x.objsubid::pg_catalog.int2, 'select')
            when 'view column' then pg_catalog.has_column_privilege($2, x.objid, x.objsubid::pg_catalog.int2, 'select')
            when 'function' then pg_catalog.has_function_privilege($2, x.objid, 'execute')
        end
        %s
        %s
        order by dist
        limit %L
    ) x
    group by
      x.objtype
    , x.objnames
    , x.objargs
    , x.classid
    , x.objid
    , x.objsubid
    , x.description
    order by min(x.dist)
    $sql$
    , _dimensions
    , catalog_id
    , case
        when objtypes is null then ''
        else pg_catalog.format('and x.objtype operator(pg_catalog.=) any(%L::pg_catalog.text[])', objtypes)
      end
    , case
        when max_dist is null then ''
        else pg_catalog.format('and (x.embedding operator(@extschema:vector@.<=>) ($1::@extschema:vector@.vector(%s))) <= %s', _dimensions, max_dist)
      end
    , "limit"
    );
    -- raise log '%', _sql;

    return query execute _sql using embedding, pg_catalog."current_user"();
end;
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- find_relevant_obj
create or replace function ai.find_relevant_obj
( prompt pg_catalog.text
, "limit" pg_catalog.int8 default 5
, objtypes pg_catalog.text[] default null
, max_dist pg_catalog.float8 default null
, catalog_name pg_catalog.name default 'default'
) returns table
( objtype pg_catalog.text
, objnames pg_catalog.text[]
, objargs pg_catalog.text[]
, classid pg_catalog.oid
, objid pg_catalog.oid
, objsubid pg_catalog.int4
, description pg_catalog.text
, dist pg_catalog.float8
)
as $func$
declare
    _catalog_id pg_catalog.int4;
    _vectorizer_id pg_catalog.int4;
    _embedding @extschema:vector@.vector;
begin
    select
      x.id
    , x.obj_vectorizer_id
    into strict
      _catalog_id
    , _vectorizer_id
    from ai.semantic_catalog x
    where x.catalog_name operator(pg_catalog.=) find_relevant_obj.catalog_name
    ;

    _embedding = ai.vectorizer_embed(_vectorizer_id, prompt);

    return query
    select *
    from ai._find_relevant_obj
    ( _catalog_id
    , _embedding
    , "limit"
    , objtypes
    , max_dist
    );
end;
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

