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
$func$ language sql stable security invoker
set search_path to pg_catalog, pg_temp
;


-------------------------------------------------------------------------------
-- _search_semantic_catalog_obj
create function ai._search_semantic_catalog_obj
( embedding @extschema:vector@.vector
, catalog_name text default 'default'
, max_results bigint default 5
, max_vector_dist float8 default null
) returns setof ai.semantic_catalog_obj
as $func$
declare
    _sql text;
begin
    select format
    ( $sql$
      select o.*
      from
      (
          select distinct e.objtype, e.objnames, e.objargs
          from
          (
            select e.*
            from %I.%I e
            inner join ai.semantic_catalog_obj o
            on
            (e.objtype operator(pg_catalog.=) o.objtype
            and e.objnames operator(pg_catalog.=) o.objnames
            and e.objargs operator(pg_catalog.=) o.objargs
            )
            where pg_catalog.has_schema_privilege(pg_catalog.current_user(), e.objnames[1], 'usage') and
            case e.objtype
                when 'table' then pg_catalog.has_table_privilege(pg_catalog.current_user(), o.objid, 'select')
                when 'view' then pg_catalog.has_table_privilege(pg_catalog.current_user(), o.objid, 'select')
                when 'table column' then pg_catalog.has_column_privilege(pg_catalog.current_user(), o.objid, o.objsubid::pg_catalog.int2, 'select')
                when 'view column' then pg_catalog.has_column_privilege(pg_catalog.current_user(), o.objid, o.objsubid::pg_catalog.int2, 'select')
                when 'function' then pg_catalog.has_function_privilege(pg_catalog.current_user(), o.objid, 'execute')
            end
            %s
            order by e.embedding operator(@extschema:vector@.<=>) $1
            limit %L
          ) e
      ) e
      inner join ai.semantic_catalog_obj o
      on
      (   e.objtype operator(pg_catalog.=) o.objtype
      and e.objnames operator(pg_catalog.=) o.objnames
      and e.objargs operator(pg_catalog.=) o.objargs
      )
    $sql$
    , v.target_schema, v.target_table
    , case when max_vector_dist is not null then 'and e.embedding operator(@extschema:vector@.<=>) $1 <= $2' else '' end
    , max_results
    )
    into strict _sql
    from ai.semantic_catalog k
    inner join ai.vectorizer v on (k.obj_vectorizer_id = v.id)
    where k.catalog_name = _search_semantic_catalog_obj.catalog_name
    ;

    raise debug '%', _sql;

    if max_vector_dist is not null then
        return query execute _sql using embedding, max_vector_dist;
    else
        return query execute _sql using embedding;
    end if;
end;
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _search_semantic_catalog_obj
create function ai._search_semantic_catalog_obj
( keywords text[]
, catalog_name text default 'default'
, max_results bigint default 5
, min_ts_rank real default null
) returns setof ai.semantic_catalog_obj
as $func$
declare
    _tsquery tsquery;
    _sql text;
begin
    -- if keywords is null or empty return an empty result set
    if keywords is null or array_length(keywords, 1) = 0 then
        return query select * from ai.semantic_catalog_obj where false;
    end if;

    -- TODO: look up the text search config on the semantic_catalog so we can use the index

    -- construct a tsquery by ORing all the keywords
    select to_tsquery(string_agg(format($$'%s'$$, keyword), ' | '))
    into strict _tsquery
    from unnest(keywords) keyword
    ;

    select format
    ( $sql$
      select o.*
      from
      (
          select distinct e.objtype, e.objnames, e.objargs
          from
          (
            select e.*
            from %I.%I e
            inner join ai.semantic_catalog_obj o on
            (e.objtype operator(pg_catalog.=) o.objtype
            and e.objnames operator(pg_catalog.=) o.objnames
            and e.objargs operator(pg_catalog.=) o.objargs
            )
            where to_tsvector(e.chunk) @@ $1
            and pg_catalog.has_schema_privilege(pg_catalog.current_user(), e.objnames[1], 'usage') and
            case e.objtype
                when 'table' then pg_catalog.has_table_privilege(pg_catalog.current_user(), o.objid, 'select')
                when 'view' then pg_catalog.has_table_privilege(pg_catalog.current_user(), o.objid, 'select')
                when 'table column' then pg_catalog.has_column_privilege(pg_catalog.current_user(), o.objid, o.objsubid::pg_catalog.int2, 'select')
                when 'view column' then pg_catalog.has_column_privilege(pg_catalog.current_user(), o.objid, o.objsubid::pg_catalog.int2, 'select')
                when 'function' then pg_catalog.has_function_privilege(pg_catalog.current_user(), o.objid, 'execute')
            end
            %s
            order by ts_rank_cd(to_tsvector(e.chunk), $1) desc
            limit %L
          ) e
      ) e
      inner join ai.semantic_catalog_obj o
      on
      (   e.objtype = o.objtype
      and e.objnames = o.objnames
      and e.objargs = o.objargs
      )
    $sql$
    , v.target_schema, v.target_table
    , case when min_ts_rank is not null then 'and ts_rank_cd(to_tsvector(e.chunk), $1) >= $2' else '' end
    , max_results
    )
    into strict _sql
    from ai.semantic_catalog k
    inner join ai.vectorizer v on (k.obj_vectorizer_id operator(pg_catalog.=) v.id)
    where k.catalog_name operator(pg_catalog.=) _search_semantic_catalog_obj.catalog_name
    ;

    raise debug '%', _sql;

    if min_ts_rank is not null then
        return query execute _sql using _tsquery, min_ts_rank;
    else
        return query execute _sql using _tsquery;
    end if;
end;
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

/*
-------------------------------------------------------------------------------
-- search_semantic_catalog_obj
create function ai.search_semantic_catalog_obj
( embedding text default null
, keywords text[] default null
, catalog_name text default 'default'
, max_results bigint default 5
, max_vector_dist float8 default null
, min_ts_rank real default null
) returns setof ai.semantic_catalog_obj
as $func$
declare
begin
    if (question is null or question = '') and (keywords is null or array_length(keywords, 1) = 0) then
        raise exception 'question and keywords must not both be null';
    end if;

    -- TODO: do a real reranking?

    return query
    select *
    from
    (
        select *
        from ai._search_semantic_catalog_obj
        ( question
        , catalog_name
        , max_results
        , max_vector_dist
        )
        union
        select *
        from ai._search_semantic_catalog_obj
        ( keywords
        , catalog_name
        , max_results
        , min_ts_rank
        )
    ) x
    -- limit max_results -- TODO: consider whether to do an outer limit or not
    ;
end;
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;
*/

-------------------------------------------------------------------------------
-- _search_semantic_catalog_sql
create function ai._search_semantic_catalog_sql
( embedding @extschema:vector@.vector
, catalog_name text default 'default'
, max_results bigint default 5
, max_vector_dist float8 default null
) returns setof ai.semantic_catalog_sql
as $func$
declare
    _sql text;
begin
    select format
    ( $sql$
    select q.*
    from
    (
        select distinct e.id
        from
        (
            select e.*
            from %I.%I e
            %s
            order by e.embedding operator(@extschema:vector@.<=>) $1
            limit %L
        ) e
    ) e
    inner join ai.semantic_catalog_sql q on (q.id = e.id)
    $sql$
    , v.target_schema, v.target_table
    , case when max_vector_dist is not null then 'where e.embedding operator(@extschema:vector@.<=>) $1 <= $2' else '' end
    , max_results
    )
    into strict _sql
    from ai.semantic_catalog k
    inner join ai.vectorizer v on (k.sql_vectorizer_id = v.id)
    where k.catalog_name = _search_semantic_catalog_sql.catalog_name
    ;

    raise debug '%', _sql;

    if max_vector_dist is not null then
        return query execute _sql using embedding, max_vector_dist;
    else
        return query execute _sql using embedding;
    end if;
end;
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _search_semantic_catalog_sql
create function ai._search_semantic_catalog_sql
( keywords text[]
, catalog_name text default 'default'
, max_results bigint default 5
, min_ts_rank real default null
) returns setof ai.semantic_catalog_sql
as $func$
declare
    _tsquery tsquery;
    _sql text;
begin
    -- if keywords is null or empty return an empty result set
    if keywords is null or array_length(keywords, 1) = 0 then
        return query select * from ai.semantic_catalog_obj where false;
    end if;

    -- construct a tsquery by ORing all the keywords
    select to_tsquery(string_agg(format($$'%s'$$, keyword), ' | '))
    into strict _tsquery
    from unnest(keywords) keyword
    ;

    -- TODO: look up the text search config on the semantic_catalog so we can use the index

    select format
    ( $sql$
    select q.*
    from
    (
        select distinct e.id
        from
        (
            select e.*
            from %I.%I e
            where to_tsvector(e.chunk) @@ $1
            %s
            order by ts_rank_cd(to_tsvector(e.chunk), $1) desc
            limit %L
        ) e
    ) e
    inner join ai.semantic_catalog_sql q on (q.id = e.id)
    $sql$
    , v.target_schema, v.target_table
    , case when min_ts_rank is not null then 'and ts_rank_cd(to_tsvector(e.chunk), $1) >= $2' else '' end
    , max_results
    )
    into strict _sql
    from ai.semantic_catalog k
    inner join ai.vectorizer v on (k.sql_vectorizer_id operator(pg_catalog.=) v.id)
    where k.catalog_name operator(pg_catalog.=) _search_semantic_catalog_sql.catalog_name
    ;

    raise debug '%', _sql;

    if min_ts_rank is not null then
        return query execute _sql using _tsquery, min_ts_rank;
    else
        return query execute _sql using _tsquery;
    end if;
end;
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

/*
-------------------------------------------------------------------------------
-- search_semantic_catalog_sql
create function ai.search_semantic_catalog_sql
( question text default null
, keywords text[] default null
, catalog_name text default 'default'
, max_results bigint default 5
, max_vector_dist float8 default null
, min_ts_rank real default null
) returns setof ai.semantic_catalog_sql
as $func$
begin
    if (question is null or question = '') and (keywords is null or array_length(keywords, 1) = 0) then
        raise exception 'question and keywords must not both be null';
    end if;

    -- TODO: do a real reranking?

    return query
    select *
    from
    (
        select *
        from ai._search_semantic_catalog_sql
        ( question
        , catalog_name
        , max_results
        , max_vector_dist
        )
        union
        select *
        from ai._search_semantic_catalog_sql
        ( keywords
        , catalog_name
        , max_results
        , min_ts_rank
        )
    ) x
--    limit max_results -- TODO: consider whether to do an outer limit or not
    ;
end;
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;
*/