do language plpgsql $block$
begin
    update ai.vectorizer
    set queue_failed_table = '_vectorizer_q_failed_' || id;
end
$block$;

do language plpgsql $block$
declare
    _sql pg_catalog.text;
    _vec ai.vectorizer;
    _grant_to text[];
begin
    -- loop through all vectorizers to extract queue tables information
    for _vec in (
        select * from ai.vectorizer
    )
    loop
        select array_agg(distinct(grantee)) into _grant_to
        from (
                 select (aclexplode(k.relacl)).grantee::regrole::text as grantee
                 from pg_class k
                     inner join pg_namespace n on (k.relnamespace = n.oid)
                 where k.relname = _vec.queue_table
                   and n.nspname = _vec.queue_schema
             ) as grants
        ;

        -- if no grantees found, use a sensible default or leave it null
        if _grant_to is null then
            _grant_to := '{}';
        end if;
        select pg_catalog.format
        ( $sql$
        create table %I.%I
        ( %s
        , created_at pg_catalog.timestamptz not null default now()
        , failure_step pg_catalog.text not null default ''
        )
        $sql$
        , _vec.queue_schema, _vec.queue_failed_table
        , (
            select pg_catalog.string_agg
            ( pg_catalog.format
              ( '%I %s not null'
              , x.attname
              , x.typname
              )
            , e'\n, '
            order by x.attnum
            )
            from pg_catalog.jsonb_to_recordset(_vec.source_pk) x(attnum int, attname name, typname name)
        )
        ) into strict _sql
        ;
        execute _sql;

        -- create the index
        select pg_catalog.format
        ( $sql$create index on %I.%I (%s)$sql$
        , _vec.queue_schema, _vec.queue_failed_table
        , (
            select pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' order by x.pknum)
            from pg_catalog.jsonb_to_recordset(_vec.source_pk) x(pknum int, attname name)
          )
        ) into strict _sql
        ;
        execute _sql;


        -- apply permissions if we found grantees
        if array_length(_grant_to, 1) > 0 then
        -- grant usage on queue schema to identified roles
        select pg_catalog.format
               ( $sql$grant usage on schema %I to %s$sql$
                   , _vec.queue_schema
                   , (
                     select pg_catalog.string_agg(pg_catalog.quote_ident(x), ', ')
                     from pg_catalog.unnest(_grant_to) x
                 )
               ) into strict _sql;

        execute _sql;

        -- grant select, update, delete on queue table to identified roles
        select pg_catalog.format
               ( $sql$grant select, insert, update, delete on %I.%I to %s$sql$
                    , _vec.queue_schema
                   , _vec.queue_failed_table
                   , (
                     select pg_catalog.string_agg(pg_catalog.quote_ident(x), ', ')
                     from pg_catalog.unnest(_grant_to) x
                 )
               ) into strict _sql;

        execute _sql;
        end if;

    end loop;
end $block$
;
