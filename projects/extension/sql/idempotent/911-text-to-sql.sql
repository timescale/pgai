--FEATURE-FLAG: text_to_sql

-------------------------------------------------------------------------------
-- _text_to_sql
create function ai._text_to_sql
( question text
, catalog_name text default 'default'
, config jsonb default null
, search_path text default pg_catalog.current_setting('search_path', true)
) returns jsonb
as $func$
declare
    _catalog_name text = _text_to_sql.catalog_name;
    _result jsonb;
begin
    if config is null then
        select x.text_to_sql into strict config
        from ai.semantic_catalog x
        where x.catalog_name = _catalog_name
        ;
    end if;

    case config->>'provider'
        when 'anthropic' then
            _result = ai._text_to_sql_anthropic
            ( question
            , catalog_name
            , config
            , search_path
            );
        when 'ollama' then
            _result = ai._text_to_sql_ollama
            ( question
            , catalog_name
            , config
            , search_path
            );
        when 'openai' then
            _result = ai._text_to_sql_openai
            ( question
            , catalog_name
            , config
            , search_path
            );
        when 'cohere' then
            _result = ai._text_to_sql_cohere
            ( question
            , catalog_name
            , config
            , search_path
            );
        else
            raise exception 'text-to-sql provider % not recognized', config->>'provider';
    end case;
    return _result;
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- text_to_sql
create function ai.text_to_sql
( question text
, catalog_name text default 'default'
, config jsonb default null
, search_path text default pg_catalog.current_setting('search_path', true)
) returns text
as $func$
declare
    _result jsonb;
begin
    _result = ai._text_to_sql
    ( question
    , catalog_name
    , config
    , search_path
    );
    if _result is not null then
        raise debug '%', jsonb_pretty(_result);
        return _result->>'sql_statement';
    end if;
    return null;
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

