do language plpgsql $block$
begin
    update ai.vectorizer
    set queue_failed_table = '_vectorizer_q_failed_' || id;
end
$block$;

do language plpgsql $block$
begin
declare
 _sql pg_catalog.text;
 _vec ai.vectorizer;
begin
    -- loop through all vectorizers to extract queue tables information
for _vec in (
        select * from ai.vectorizer
    )
    loop

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
                    (
                            pg_catalog.format
                            ( '%I %s not null'
                                , x.attname
                                , x.typname
                            )
                        , E'\n, '
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

if grant_to is not null then
        -- grant usage on queue schema to grant_to roles
select pg_catalog.format
       ( $sql$grant usage on schema %I to %s$sql$
           , _vec.queue_schema
           , (
             select pg_catalog.string_agg(pg_catalog.quote_ident(x), ', ')
             from pg_catalog.unnest(_vec.grant_to) x
         )
       ) into strict _sql;
execute _sql;

-- grant select, update, delete on queue table to grant_to roles
select pg_catalog.format
       ( $sql$grant select, insert, update, delete on %I.%I to %s$sql$
        , _vec.queue_schema
           , _vec.queue_failed_table
           , (
             select pg_catalog.string_agg(pg_catalog.quote_ident(x), ', ')
             from pg_catalog.unnest(_vec.grant_to) x
         )
       ) into strict _sql;
execute _sql;
end if;
end loop;
end;
$block$;
