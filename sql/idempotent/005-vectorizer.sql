
/*
    -- check that source columns match real columns
    if (
        select pg_catalog.count(*) operator(pg_catalog.!=) pg_catalog.array_length(_source_cols, 1)
        from pg_attribute a
        where a.attrelid operator(pg_catalog.=) _source_table
        and a.attname operator( pg_catalog.=) any(_source_cols)
    ) then
        raise exception 'invalid source column specification';
    end if;

    -- only support one source column at the moment
    if pg_catalog.array_length(_source_cols, 1) > 1 then
        raise exception 'only one source column supported';
    end if;
*/



-------------------------------------------------------------------------------
-- vectorize_async
create or replace function ai.vectorize_async
( _source_table regclass
, _dimensions int
, _config jsonb
, _target_schema name default null
, _target_table name default null
, _target_column name default null
, _queue_schema name default null
, _queue_table name default null
) returns int
as $func$
declare
    _source_table_name name;
    _source_schema name;
    _trigger_schema name;
    _trigger_name name;
    _pk jsonb;
    _sql text;
    _id int;
begin
    -- get source table name and schema name
    select k.relname, n.nspname
    into strict _source_table_name, _source_schema
    from pg_catalog.pg_class k
    inner join pg_catalog.pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
    where k.oid operator(pg_catalog.=) _source_table
    ;

    if _dimensions is null then
        raise exception '_dimensions argument is required';
    end if;
    _target_schema = coalesce(_target_schema, _source_schema);
    _target_table = coalesce(_target_table, pg_catalog.concat(_source_table_name, '_embedding'));
    _target_column = coalesce(_target_column, 'embedding');
    _queue_schema = coalesce(_queue_schema, _target_schema);
    _queue_table = coalesce(_queue_table, pg_catalog.concat(_target_table, '_q'));
    _trigger_schema = _target_schema;
    _trigger_name = _target_table;

    -- get the source table's primary key definition
    select jsonb_agg(x) into strict _pk
    from
    (
        select e.attnum, e.pknum, a.attname, y.typname, a.attnotnull
        from pg_catalog.pg_constraint k
        cross join lateral unnest(k.conkey) with ordinality e(attnum, pknum)
        inner join pg_catalog.pg_attribute a
            on (k.conrelid operator(pg_catalog.=) a.attrelid
                and e.attnum operator(pg_catalog.=) a.attnum)
        inner join pg_catalog.pg_type y on (a.atttypid operator(pg_catalog.=) y.oid)
        where k.conrelid operator(pg_catalog.=) _source_table
        and k.contype operator(pg_catalog.=) 'p'
    ) x
    ;
    if jsonb_array_length(_pk) = 0 then
        raise exception 'source table must have a primary key constraint';
    end if;

    -- create the target table
    select pg_catalog.format
    ( $sql$
    create table %I.%I
    ( %s
    , chunk_seq int not null
    , chunk text not null
    , %I @extschema:vector@.vector(%L) not null
    , primary key (%s, chunk_seq)
    , foreign key (%s) references %I.%I (%s) on delete cascade
    )
    $sql$
    , _target_schema, _target_table
    , (
        select pg_catalog.string_agg
        (
            pg_catalog.format
            ( '%I %s %s'
            , x.attname
            , x.typname
            , case x.attnotnull when true then 'not null' else '' end
            )
            , E'\n, '
            order by x.attnum
        )
        from pg_catalog.jsonb_to_recordset(_pk)
            x(attnum int, attname name, typname name, attnotnull bool)
      )
    , _target_column, _dimensions
    , (
        select pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' order by x.pknum)
        from pg_catalog.jsonb_to_recordset(_pk) x(pknum int, attname name)
      )
    , (
        select pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' order by x.pknum)
        from pg_catalog.jsonb_to_recordset(_pk) x(pknum int, attname name)
      )
    , _source_schema, _source_table_name
    , (
        select pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' order by x.pknum)
        from pg_catalog.jsonb_to_recordset(_pk) x(pknum int, attname name)
      )
    ) into strict _sql
    ;
    execute _sql;

    -- create queue table
    select pg_catalog.format
    ( $sql$create table %I.%I(%s, at timestamptz not null default now())$sql$
    , _queue_schema, _queue_table
    , (
        select pg_catalog.string_agg
        (
          pg_catalog.format
          ( '%I %s %s'
          , x.attname
          , x.typname
          , case x.attnotnull when true then 'not null' else '' end
          )
          , E'\n, '
          order by x.attnum
        )
        from pg_catalog.jsonb_to_recordset(_pk) x(attnum int, attname name, typname name, attnotnull bool)
      )
    ) into strict _sql
    ;
    execute _sql;

    -- create index on queue table
    select pg_catalog.format
    ( $sql$create index on %I.%I (%s)$sql$
    , _queue_schema, _queue_table
    , (
        select pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' order by x.pknum)
        from pg_catalog.jsonb_to_recordset(_pk) x(pknum int, attname name)
      )
    ) into strict _sql
    ;
    execute _sql;

    -- create trigger func
    select pg_catalog.format
    ( $sql$
    create function %I.%I() returns trigger
    as $plpgsql$
    begin
        if TG_OP = 'DELETE' then
            insert into %I.%I (%s)
            values (%s);
        else
            insert into %I.%I (%s)
            values (%s);
        end if;
        return null;
    end;
    $plpgsql$ language plpgsql
    $sql$
    , _trigger_schema, _trigger_name
    , _queue_schema, _queue_table
    , (
        select pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' order by x.attnum)
        from pg_catalog.jsonb_to_recordset(_pk) x(attnum int, attname name)
      )
    , (
        select pg_catalog.string_agg(pg_catalog.format('OLD.%I', x.attname), ', ' order by x.attnum)
        from pg_catalog.jsonb_to_recordset(_pk) x(attnum int, attname name)
      )
    , _queue_schema, _queue_table
    , (
        select pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' order by x.attnum)
        from pg_catalog.jsonb_to_recordset(_pk) x(attnum int, attname name)
      )
    , (
        select pg_catalog.string_agg(pg_catalog.format('NEW.%I', x.attname), ', ' order by x.attnum)
        from pg_catalog.jsonb_to_recordset(_pk) x(attnum int, attname name)
      )
    ) into strict _sql
    ;
    execute _sql;

    -- create trigger on source table
    select pg_catalog.format
    ( $sql$
    create trigger %I
    after insert or update or delete
    on %I.%I
    for each row execute function %I.%I();
    $sql$
    , _trigger_name
    , _source_schema, _source_table_name
    , _trigger_schema, _trigger_name
    ) into strict _sql
    ;
    execute _sql;

    -- insert into queue any existing rows from source table
    select format
    ( $sql$
    insert into %I.%I (%s)
    select %s
    from %I.%I x
    ;
    $sql$
    , _queue_schema, _queue_table
    , (
        select pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' order by x.attnum)
        from pg_catalog.jsonb_to_recordset(_pk) x(attnum int, attname name)
      )
    , (
        select pg_catalog.string_agg(pg_catalog.format('x.%I', x.attname), ', ' order by x.attnum)
        from pg_catalog.jsonb_to_recordset(_pk) x(attnum int, attname name)
      )
    , _source_schema, _source_table_name
    ) into strict _sql
    ;
    execute _sql;

    raise notice 'who am i: %', current_user;
    raise notice 'do i have insert: %', (select has_table_privilege('test', 'ai.vectorize', 'insert'));
    raise notice 'do i have usage: %', (select has_sequence_privilege('test', 'ai.vectorize_id_seq', 'usage'));

    insert into ai.vectorize
    ( source_schema
    , source_table
    , target_schema
    , target_table
    , target_column
    , queue_schema
    , queue_table
    , config
    )
    values
    ( _source_schema
    , _source_table_name
    , _target_schema
    , _target_table
    , _target_column
    , _queue_schema
    , _queue_table
    , _config
    )
    returning id into strict _id;
    return _id;
end
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;
