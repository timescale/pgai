--FEATURE-FLAG: text_to_sql

-------------------------------------------------------------------------------
-- text_to_sql_render_prompt
create function ai.text_to_sql_render_prompt
( question text
, obj_prompt text
, samples_sql text
, sql_prompt text
, query_err jsonb default null
) returns text
as $func$
declare
    _header text;
    _query_err text;
    _prompt text;
begin
    select concat_ws
    ( E'\n'
    , $$Below are descriptions of database objects and examples of SQL statements that are meant to give context to a user's question.$$
    , $$Analyze the context provided. Identify the elements that are relevant to the user's question.$$
    , $$ONLY use database elements that have been described to you unless they are built-in to Postgres. If more context is needed, use the "request_more_context_by_question" tool to ask questions about the database model.$$
    , $$If enough context has been provided to confidently address the question, use the "answer_user_question_with_sql_statement" tool to record your final answer in the form of a valid SQL statement.$$
    , $$Fully qualify all database elements.$$
    ) into strict _header
    ;
    
    if query_err is not null then
        select concat_ws
        ( E'\n'
        , $$The following query is not valid:$$
        , $$```sql$$
        , query_err->>'query'
        , $$```$$
        , $$It produces the following error:$$
        , query_err->>'error'
        ) into strict _query_err
        ;
    end if;
    
    select concat_ws
    ( E'\n\n'
    , _header
    , coalesce(obj_prompt, '')
    , coalesce(samples_sql, '')
    , coalesce(sql_prompt, '')
    , coalesce(_query_err, '')
    , concat('Q: ', question)
    ) into strict _prompt
    ;
    
    return _prompt;
end
$func$ language plpgsql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _text_to_sql_explain
create function ai._text_to_sql_explain
( sql text
) returns jsonb
as $func$
declare
    _search_path text;
    _query_plan jsonb;
    _msg text;
    _detail text;
    _hint text;
    _error text;
begin
    execute 'show search_path' into _search_path;
    raise debug 'search_path: %', _search_path;
    begin
        execute pg_catalog.format($$explain (verbose, format json) %s$$, sql) 
        into strict _query_plan;
    exception when others then
        get stacked diagnostics
          _msg = message_text
        , _detail = pg_exception_detail
        , _hint = pg_exception_hint
        ;
        _error = concat_ws(E'\n', _msg, _detail, _hint);
        raise notice 'BAD QUERY: %', _error;
    end;
    
    return json_object
    ( 'failed': (_msg is not null)
    , 'query': sql
    , 'query_plan': _query_plan
    , 'error': _error
    absent on null
    );
end
$func$ language plpgsql volatile security invoker
-- do not set an explicit search_path
-- we want to use the search_path of the caller
;
