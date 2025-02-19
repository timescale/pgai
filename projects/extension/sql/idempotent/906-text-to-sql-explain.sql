--FEATURE-FLAG: text_to_sql

-------------------------------------------------------------------------------
-- _text_to_sql_explain
create or replace function ai._text_to_sql_explain
( sql text
, search_path text default pg_catalog.current_setting('search_path')
, out valid bool
, out err_msg text
, out query_plan jsonb
)
as $func$
declare
    _msg text;
    _detail text;
    _hint text;
begin
    execute pg_catalog.format('set local search_path to %s', search_path);
    begin
        execute pg_catalog.format('explain (verbose, format json) %s', sql) 
        into strict query_plan;
        valid = true;
    exception when others then
        valid = false;
        get stacked diagnostics
          _msg = message_text
        , _detail = pg_exception_detail
        , _hint = pg_exception_hint
        ;
        err_msg = concat_ws(E'\n', _msg, _detail, _hint);
    end;
    set local search_path to pg_catalog, pg_temp;
end
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;
