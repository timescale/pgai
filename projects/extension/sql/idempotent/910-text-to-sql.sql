--FEATURE-FLAG: text_to_sql

-------------------------------------------------------------------------------
-- _text_to_sql
create function ai._text_to_sql
( question text
, catalog_name text default 'default'
, config jsonb default null
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
            );
        when 'ollama' then
            _result = ai._text_to_sql_ollama
            ( question
            , catalog_name
            , config
            );
        when 'openai' then
            _result = ai._text_to_sql_openai
            ( question
            , catalog_name
            , config
            );
        when 'cohere' then
            _result = ai._text_to_sql_cohere
            ( question
            , catalog_name
            , config
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
) returns text
as $func$
declare
    _result jsonb;
begin
    _result = ai._text_to_sql
    ( question
    , catalog_name
    , config
    );
    if _result is not null then
        return _result->>'sql_statement';
    end if;
    return null;
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

