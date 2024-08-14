

-------------------------------------------------------------------------------
-- execute_vectorizer
create or replace function ai.execute_vectorizer(_vectorizer_id int, _force bool default false) returns int
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.vectorizer
    return ai.vectorizer.execute_vectorizer(plpy, _vectorizer_id, _force)
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- embedding_config_openai
create or replace function ai.embedding_config_openai
( _model text
, _dimensions int default null
, _user text default null
) returns jsonb
as $func$
    select json_object
    ( 'provider': 'openai'
    , 'model': _model
    , 'dimensions': _dimensions
    , 'user': _user
    absent on null
    )
$func$ language sql immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- chunking_config_token_text_splitter
create or replace function ai.chunking_config_token_text_splitter
( _column name
, _chunk_size int
, _chunk_overlap int
, _separator text default ' '
) returns jsonb
as $func$
    select pg_catalog.jsonb_build_object
    ( 'implementation', 'token_text_splitter'
    , 'chunk_column', _column
    , 'chunk_size', _chunk_size
    , 'chunk_overlap', _chunk_overlap
    , 'separator', _separator
    )
$func$ language sql immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- formatting_config_python_string_template
create or replace function ai.formatting_config_python_string_template
( _columns name[]
, _template text
) returns jsonb
as $func$
    select pg_catalog.jsonb_build_object
    ( 'implementation', 'python_string_template'
    , 'columns', _columns
    , 'template', _template
    )
$func$ language sql immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _vectorizer_source_pk
create or replace function ai._vectorizer_source_pk(_source_table regclass) returns jsonb as
$func$
    select pg_catalog.jsonb_agg(x)
    from
    (
        select e.attnum, e.pknum, a.attname, y.typname, a.attnotnull
        from pg_catalog.pg_constraint k
        cross join lateral pg_catalog.unnest(k.conkey) with ordinality e(attnum, pknum)
        inner join pg_catalog.pg_attribute a
            on (k.conrelid operator(pg_catalog.=) a.attrelid
                and e.attnum operator(pg_catalog.=) a.attnum)
        inner join pg_catalog.pg_type y on (a.atttypid operator(pg_catalog.=) y.oid)
        where k.conrelid operator(pg_catalog.=) _source_table
        and k.contype operator(pg_catalog.=) 'p'
    ) x
$func$
language sql stable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _vectorizer_create_target_table
create or replace function ai._vectorizer_create_target_table
( _source_schema name
, _source_table name
, _source_pk jsonb
, _target_schema name
, _target_table name
, _target_column name
, _dimensions int
) returns void as
$func$
declare
    _pk_cols text;
    _sql text;
begin
    select pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' order by x.pknum)
    into strict _pk_cols
    from pg_catalog.jsonb_to_recordset(_source_pk) x(pknum int, attname name)
    ;
    select pg_catalog.format
    ( $sql$
    create table %I.%I
    ( id uuid not null primary key default pg_catalog.gen_random_uuid()
    , %s
    , chunk_seq int not null
    , chunk text not null
    , %I @extschema:vector@.vector(%L) not null
    , unique (%s, chunk_seq)
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
        from pg_catalog.jsonb_to_recordset(_source_pk)
            x(attnum int, attname name, typname name, attnotnull bool)
      )
    , _target_column, _dimensions
    , _pk_cols
    , _pk_cols
    , _source_schema, _source_table
    , _pk_cols
    ) into strict _sql
    ;
    execute _sql;
end;
$func$
language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _vectorizer_create_queue_table
create or replace function ai._vectorizer_create_queue_table
( _queue_table name
, _source_pk jsonb
) returns void as
$func$
declare
    _sql text;
begin
    select pg_catalog.format
    ( $sql$create table ai.%I(%s, queued_at timestamptz not null default now())$sql$
    , _queue_table
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
        from pg_catalog.jsonb_to_recordset(_source_pk) x(attnum int, attname name, typname name, attnotnull bool)
      )
    ) into strict _sql
    ;
    execute _sql;

    select pg_catalog.format
    ( $sql$create index on ai.%I (%s)$sql$
    , _queue_table
    , (
        select pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' order by x.pknum)
        from pg_catalog.jsonb_to_recordset(_source_pk) x(pknum int, attname name)
      )
    ) into strict _sql
    ;
    execute _sql;
end;
$func$
language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _vectorizer_create_source_trigger
create or replace function ai._vectorizer_create_source_trigger
( _trigger_name name
, _queue_table name
, _source_schema name
, _source_table name
, _source_pk jsonb
) returns void as
$func$
declare
    _sql text;
begin
    select pg_catalog.format
    ( $sql$
    create function ai.%I() returns trigger
    as $plpgsql$
    begin
        insert into ai.%I (%s)
        values (%s);
        return null;
    end;
    $plpgsql$ language plpgsql
    $sql$
    , _trigger_name
    , _queue_table
    , _queue_table
    , (
        select pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' order by x.attnum)
        from pg_catalog.jsonb_to_recordset(_source_pk) x(attnum int, attname name)
      )
    , (
        select pg_catalog.string_agg(pg_catalog.format('new.%I', x.attname), ', ' order by x.attnum)
        from pg_catalog.jsonb_to_recordset(_source_pk) x(attnum int, attname name)
      )
    ) into strict _sql
    ;
    execute _sql;

    select pg_catalog.format
    ( $sql$
    create trigger %I
    after insert or update
    on %I.%I
    for each row execute function ai.%I();
    $sql$
    , _trigger_name
    , _source_schema, _source_table
    , _trigger_name
    ) into strict _sql
    ;
    execute _sql;
end;
$func$
language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _vectorizer_create_queue_trigger
create or replace function ai._vectorizer_create_queue_trigger
( _queue_table name
, _target_schema name
, _target_table name
) returns void as
$func$
declare
    _sql text;
begin
    select pg_catalog.format
    ( $sql$
    create function ai.%I() returns trigger
    as $plpgsql$
    begin
        perform ai.execute_vectorizer(v.id)
        from ai.vectorizer v
        where v.target_schema = %L
        and v.target_table = %L
        ;
        return null;
    end;
    $plpgsql$ language plpgsql
    $sql$
    , _queue_table
    , _target_schema
    , _target_table
    ) into strict _sql
    ;
    execute _sql;

    -- create trigger on queue table
    select pg_catalog.format
    ( $sql$
    create trigger %I after insert on ai.%I
    for each statement execute function ai.%I();
    $sql$
    , _queue_table
    , _queue_table
    , _queue_table
    ) into strict _sql
    ;
    execute _sql;
end;
$func$
language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- create_vectorizer
create or replace function ai.create_vectorizer
( _source regclass
, _dimensions int
, _embedding jsonb
, _chunking jsonb
, _formatting jsonb
, _asynchronous bool default true
, _external bool default true
, _target_schema name default null
, _target_table name default null
, _target_column name default null
) returns int
as $func$
declare
    _source_table name;
    _source_schema name;
    _source_pk jsonb;
    _vectorizer_id int;
    _queue_table name;
    _trigger_name name;
    _sql text;
    _id int;
begin
    if _asynchronous and not _external then
        raise exception 'asynchronous internal vectorizers are not implemented yet';
    end if;

    if not _asynchronous and not _external then
        raise exception 'synchronous internal vectorizers are not implemented yet';
    end if;

    if not _asynchronous and _external then
        raise exception 'synchronous vectorizers must be internal';
    end if;

    -- get source table name and schema name
    select k.relname, n.nspname
    into strict _source_table, _source_schema
    from pg_catalog.pg_class k
    inner join pg_catalog.pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
    where k.oid operator(pg_catalog.=) _source
    ;

    if _dimensions is null then
        raise exception '_dimensions argument is required';
    end if;
    _target_schema = coalesce(_target_schema, _source_schema);
    _target_table = coalesce(_target_table, pg_catalog.concat(_source_table, '_embedding'));
    _target_column = coalesce(_target_column, 'embedding');

    -- get the source table's primary key definition
    select ai._vectorizer_source_pk(_source) into strict _source_pk;
    if pg_catalog.jsonb_array_length(_source_pk) = 0 then
        raise exception 'source table must have a primary key constraint';
    end if;

    _vectorizer_id = pg_catalog.nextval('ai.vectorizer_id_seq'::pg_catalog.regclass);
    _queue_table = pg_catalog.concat('vectorizer_q_', _vectorizer_id);
    _trigger_name = pg_catalog.concat('vectorizer_trg_', _vectorizer_id);

    -- create the target table
    perform ai._vectorizer_create_target_table
    ( _source_schema
    , _source_table
    , _source_pk
    , _target_schema
    , _target_table
    , _target_column
    , _dimensions
    );

    -- create queue table
    perform ai._vectorizer_create_queue_table
    ( _queue_table
    , _source_pk
    );

    -- create trigger on source table to populate queue
    perform ai._vectorizer_create_source_trigger
    ( _trigger_name
    , _queue_table
    , _source_schema
    , _source_table
    , _source_pk
    );

    -- create trigger func to request an execution
    perform ai._vectorizer_create_queue_trigger
    ( _queue_table
    , _target_schema
    , _target_table
    );

    insert into ai.vectorizer
    ( id
    , asynchronous
    , external
    , source_schema
    , source_table
    , source_pk
    , target_schema
    , target_table
    , target_column
    , queue_schema
    , queue_table
    , config
    )
    values
    ( _vectorizer_id
    , _asynchronous
    , _external
    , _source_schema
    , _source_table
    , _source_pk
    , _target_schema
    , _target_table
    , _target_column
    , 'ai'
    , _queue_table
    , pg_catalog.jsonb_build_object
      ( 'version', '@extversion@'
      , 'embedding', _embedding
      , 'chunking', _chunking
      , 'formatting', _formatting
      )
    );

    -- insert into queue any existing rows from source table
    select pg_catalog.format
    ( $sql$
    insert into ai.%I (%s)
    select %s
    from %I.%I x
    ;
    $sql$
    , _queue_table
    , (
        select pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' order by x.attnum)
        from pg_catalog.jsonb_to_recordset(_source_pk) x(attnum int, attname name)
      )
    , (
        select pg_catalog.string_agg(pg_catalog.format('x.%I', x.attname), ', ' order by x.attnum)
        from pg_catalog.jsonb_to_recordset(_source_pk) x(attnum int, attname name)
      )
    , _source_schema, _source_table
    ) into strict _sql
    ;
    execute _sql;

    return _vectorizer_id;
end
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;
