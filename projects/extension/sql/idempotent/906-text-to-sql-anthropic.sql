--FEATURE-FLAG: text_to_sql

-------------------------------------------------------------------------------
-- text_to_sql_anthropic
create or replace function ai.text_to_sql_anthropic
( model text default null
, max_tokens int default 1024
, api_key text default null
, api_key_name text default null
, base_url text default null
, timeout float8 default null
, max_retries int default null
, user_id text default null
, stop_sequences text[] default null
, temperature float8 default null
, top_k int default null
, top_p float8 default null
, max_results bigint default null
, max_vector_dist float8 default null
, max_iter int2 default null
, obj_renderer regprocedure default null
, sql_renderer regprocedure default null
, user_prompt text default null
, system_prompt text default null
) returns jsonb
as $func$
    select json_object
    ( 'provider': 'anthropic'
    , 'config_type': 'text_to_sql'
    , 'model': model
    , 'max_tokens': max_tokens
    , 'api_key': api_key
    , 'api_key_name': api_key_name
    , 'base_url': base_url
    , 'timeout': timeout
    , 'max_retries': max_retries
    , 'user_id': user_id
    , 'stop_sequences': stop_sequences
    , 'temperature': temperature
    , 'top_k': top_k
    , 'top_p': top_p
    , 'max_results': max_results
    , 'max_vector_dist': max_vector_dist
    , 'max_iter': max_iter
    , 'obj_renderer': obj_renderer
    , 'sql_renderer': sql_renderer
    , 'user_prompt': user_prompt
    , 'system_prompt': system_prompt
    absent on null
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _text_to_sql_anthropic
create function ai._text_to_sql_anthropic
( question text
, catalog_name text default 'default'
, config jsonb default null
) returns jsonb
as $func$
declare
    _config jsonb = config;
    _catalog_name text = catalog_name;
    _max_iter int2;
    _iter_remaining int2;
    _max_results int8;
    _max_vector_dist float8;
    _obj_renderer regprocedure;
    _sql_renderer regprocedure;
    _model text;
    _max_tokens int4;
    _api_key text;
    _api_key_name text;
    _base_url text;
    _timeout float8;
    _max_retries int4;
    _user_id text;
    _stop_sequences text[];
    _temperature float8;
    _top_k int4;
    _top_p float8;
    _questions jsonb = jsonb_build_array(question);
    _questions_embedded @extschema:vector@.vector[];
    _ctx_obj jsonb = jsonb_build_array();
    _ctx_sql jsonb = jsonb_build_array();
    _sql text;
    _prompt_obj text;
    _prompt_sql text;
    _samples jsonb = '{}';
    _samples_sql text;
    _prompt_header text;
    _prompt text;
    _system_prompt text;
    _tools jsonb;
    _response jsonb;
    _message record;
    _answer text;
begin
    -- if a config was provided, use the settings available. defaults where missing
    -- if no config provided, use defaults for everything
    _max_iter = coalesce((_config->>'max_iter')::int2, 10);
    _iter_remaining = _max_iter;
    _max_results = coalesce((_config->>'max_results')::int8, 5);
    _max_vector_dist = (_config->>'max_vector_dist')::float8;
    _obj_renderer = coalesce((_config->>'obj_renderer')::pg_catalog.regprocedure, 'ai.render_semantic_catalog_obj(bigint, oid, oid)'::pg_catalog.regprocedure);
    _sql_renderer = coalesce((_config->>'sql_renderer')::pg_catalog.regprocedure, 'ai.render_semantic_catalog_sql(bigint, text, text)'::pg_catalog.regprocedure);
    _model = coalesce(_config->>'model', 'claude-3-5-sonnet-latest');
    _max_tokens = coalesce(_config operator(pg_catalog.->>) 'max_tokens', '1024')::int4;
    _api_key = _config operator(pg_catalog.->>) 'api_key';
    _api_key_name = _config operator(pg_catalog.->>) 'api_key_name';
    _base_url = _config operator(pg_catalog.->>) 'base_url';
    _timeout = (_config operator(pg_catalog.->>) 'timeout')::float8;
    _max_retries = (_config operator(pg_catalog.->>) 'max_retries')::int4;
    _user_id = _config operator(pg_catalog.->>) 'user_id';
    _stop_sequences = (select pg_catalog.array_agg(x) from pg_catalog.jsonb_array_elements_text(_config operator(pg_catalog.->) 'stop_sequences') x);
    _temperature = (_config operator(pg_catalog.->>) 'temperature')::float8;
    _top_k = (_config operator(pg_catalog.->>) 'top_k')::int4;
    _top_p = (_config operator(pg_catalog.->>) 'top_p')::float8;
    _system_prompt = coalesce
        ( _config->>'system_prompt'
        , concat_ws
          ( ' '
          , 'You are an expert at analyzing PostgreSQL database schemas and writing SQL statements to answer questions.'
          , 'You have access to tools.'
          )
        );
    _prompt_header = concat_ws
        ( E'\n'
        , $$Below are descriptions of database objects and examples of SQL statements that are meant to give context to a user's question.$$
        , $$Analyze the context provided. Identify the elements that are relevant to the user's question.$$
        , $$ONLY use database elements that have been described to you. If more context is needed, use the "request_more_context_by_question" tool to ask questions about the database model.$$
        , $$If enough context has been provided to confidently address the question, use the "answer_user_question_with_sql_statement" tool to record your final answer in the form of a valid SQL statement.$$
        , coalesce(_config operator(pg_catalog.->>) 'user_prompt', '')
        );

    while _iter_remaining > 0 loop
        raise debug 'iteration: %', (_max_iter - _iter_remaining + 1);
        raise debug 'searching with % questions', jsonb_array_length(_questions);

        -- search -------------------------------------------------------------

        -- embed questions
        if jsonb_array_length(_questions) > 0 then
            raise debug 'embedding % questions', jsonb_array_length(_questions);
            select array_agg(ai._semantic_catalog_embed(k.id, q))
            into strict _questions_embedded
            from ai.semantic_catalog k
            cross join jsonb_array_elements_text(_questions) q
            where k.catalog_name = _catalog_name
            ;
        end if;

        -- search obj
        if jsonb_array_length(_questions) > 0 then
            raise debug 'searching for database objects';
            select jsonb_agg(x.obj)
            into _ctx_obj
            from
            (
                select jsonb_build_object
                ( 'id', row_number() over (order by x.objid)
                , 'classid', x.classid
                , 'objid', x.objid
                ) as obj
                from
                (
                    -- search for relevant objects
                    -- if a column matches, we want to render the whole table/view, so discard the objsubid
                    -- semantic search
                    select distinct x.classid, x.objid
                    from unnest(_questions_embedded) q
                    cross join lateral ai._search_semantic_catalog_obj
                    ( q
                    , catalog_name
                    , _max_results
                    , _max_vector_dist
                    ) x
                    union
                    -- unroll objects previously marked as relevant
                    select *
                    from jsonb_to_recordset(_ctx_obj) r(classid oid, objid oid)
                ) x
            ) x
            ;
            raise debug 'search found % database objects', jsonb_array_length(_ctx_obj);
        end if;

        -- search sql
        if jsonb_array_length(_questions) > 0 then
            raise debug 'searching for sql examples';
            select jsonb_agg(x)
            into _ctx_sql
            from
            (
                -- search for relevant sql examples
                -- semantic search
                select distinct x.id, x.sql, x.description
                from unnest(_questions_embedded) q
                cross join lateral ai._search_semantic_catalog_sql
                ( q
                , catalog_name
                , _max_results
                , _max_vector_dist
                ) x
                union
                -- unroll sql examples previously marked as relevant
                select *
                from jsonb_to_recordset(_ctx_sql) r(id int, sql text, description text)
            ) x
            ;
            raise debug 'search found % sql examples', coalesce(jsonb_array_length(_ctx_sql), 0);
        end if;

        -- reset our search params
        _questions = jsonb_build_array();
        _questions_embedded = null;

        -- render prompt ------------------------------------------------------
        -- render obj
        raise debug 'rendering database objects';
        select format
        ( $sql$
        select string_agg(%I.%I(x.id, x.classid, x.objid), E'\n\n')
        from jsonb_to_recordset($1) x(id bigint, classid oid, objid oid)
        $sql$
        , n.nspname
        , f.proname
        )
        into strict _sql
        from pg_proc f
        inner join pg_namespace n on (f.pronamespace = n.oid)
        where f.oid = _obj_renderer::oid
        ;
        execute _sql using _ctx_obj into _prompt_obj;

        -- render samples
        raise debug 'rendering table samples';
        select string_agg(value, E'\n\n')
        into strict _samples_sql
        from jsonb_each_text(_samples)
        ;

        -- render sql
        raise debug 'rendering sql examples';
        select format
        ( $sql$
        select string_agg(%I.%I(x.id, x.sql, x.description), E'\n\n')
        from jsonb_to_recordset($1) x(id int, sql text, description text)
        $sql$
        , n.nspname
        , f.proname
        )
        into strict _sql
        from pg_proc f
        inner join pg_namespace n on (f.pronamespace = n.oid)
        where f.oid = _sql_renderer::oid
        ;
        execute _sql using _ctx_sql into _prompt_sql;

        -- render the user prompt
        raise debug 'rendering user prompt';
        _prompt = concat_ws
        ( E'\n'
        , _prompt_header
        , coalesce(_prompt_obj, '')
        , coalesce(_samples_sql, '')
        , coalesce(_prompt_sql, '')
        , concat('Q: ', question)
        );
        raise debug '%', _prompt;

        -- call llm -----------------------------------------------------------
        _tools = $json$
        [
            {
                "name": "request_more_context_by_question",
                "description": "If you do not have enough context to confidently answer the user's question, use this tool to ask for more context by providing a question to be used for semantic search.",
                "input_schema": {
                    "type": "object",
                    "properties" : {
                        "question": {
                            "type": "string",
                            "description": "A new natural language question relevant to the user's question that will be used to perform a semantic search to gather more context"
                        }
                    },
                    "required": ["question"]
                }
            },
            {
                "name": "request_table_sample",
                "description": "If you do not have enough context about a table to confidently answer the user's question, use this tool to ask for a sample of the table's data.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The fully qualified `schema.name` of the table or view to sample."
                        },
                        "total": {
                            "type": "integer",
                            "description": "The total number of rows to return in the sample, the max is 10."
                        }
                    },
                    "required": ["name", "total"]
                }
            },
            {
                "name": "answer_user_question_with_sql_statement",
                "description": "If you have enough context to confidently answer the user's question, use this tool to provide the answer in the form of a valid PostgreSQL SQL statement.",
                "input_schema": {
                    "type": "object",
                    "properties" : {
                        "sql_statement": {
                            "type": "string",
                            "description": "A valid SQL statement that addresses the user's question."
                        },
                        "relevant_database_object_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Provide a list of the ids of the database examples which were relevant to the user's question and useful in providing the answer."
                        },
                        "relevant_sql_example_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Provide a list of the ids of the SQL examples which were relevant to the user's question and useful in providing the answer."
                        }
                    },
                    "required": ["sql_statement"]
                }
            }
        ]
        $json$::jsonb
        ;

        raise debug 'calling llm';
        select ai.anthropic_generate
        ( _model
        , jsonb_build_array(jsonb_build_object('role', 'user', 'content', _prompt))
        , system_prompt=>_system_prompt
        , tools=>_tools
        , max_tokens=>_max_tokens
        , api_key=>_api_key
        , api_key_name=>_api_key_name
        , base_url=>_base_url
        , timeout=>_timeout
        , max_retries=>_max_retries
        , user_id=>_user_id
        , stop_sequences=>_stop_sequences
        , temperature=>_temperature
        , top_k=>_top_k
        , top_p=>_top_p
        ) into strict _response
        ;

        -- process the response -----------------------------------------------
        raise debug 'stop_reason: %', _response->>'stop_reason';
        raise debug 'received % messages', jsonb_array_length(_response->'content');
        raise debug '%', jsonb_pretty(_response->'content');
        for _message in
        (
            select m.*
            from jsonb_to_recordset(_response->'content') m
            ( type text
            , text text
            , id text
            , name text
            , input jsonb
            )
        )
        loop
            case _message.type
                when 'text' then
                    raise debug '%', _message.text;
                when 'tool_use' then
                    case _message.name
                        when 'request_more_context_by_question' then
                            raise debug 'tool use: request_more_context_by_question: %', _message.input->'question';
                            -- append the question to the list of questions to use on the next iteration
                            select _questions || jsonb_build_array(_message.input->'question')
                            into strict _questions
                            ;
                        when 'request_table_sample' then
                            raise debug 'tool use: request_table_sample: %', _message.input;
                            select _samples || jsonb_build_object(_message.input->>'name', ai.render_sample((_message.input->>'name')::regclass, (_message.input->>'total')::int4))
                            into strict _samples
                            ;
                        when 'answer_user_question_with_sql_statement' then
                            raise debug 'tool use: answer_user_question_with_sql_statement';
                            select _message.input->>'sql_statement' into strict _answer;
                            if _message.input->'relevant_database_object_ids' is not null and jsonb_array_length(_message.input->'relevant_database_object_ids') > 0 then
                                -- throw out any obj that the LLM did NOT mark as relevant
                                select jsonb_agg(r) into _ctx_obj
                                from jsonb_array_elements_text(_message.input->'relevant_database_object_ids') i
                                inner join jsonb_to_recordset(_ctx_obj) r(id bigint, classid oid, objid oid)
                                on (i::bigint = r.id)
                                ;
                            end if;
                            if _message.input->'relevant_sql_example_ids' is not null and jsonb_array_length(_message.input->'relevant_sql_example_ids') > 0 then
                                -- throw out any sql that the LLM did NOT mark as relevant
                                select jsonb_agg(r) into _ctx_sql
                                from jsonb_array_elements_text(_message.input->'relevant_sql_example_ids') i
                                inner join jsonb_to_recordset(_ctx_sql) r(id bigint, sql text, description text)
                                on (i::int = r.id)
                                ;
                            end if;
                    end case
                    ;
            end case
            ;
            -- if we got our answer, return
            if _answer is not null then
                raise debug 'relevant database objects %', jsonb_pretty(_ctx_obj);
                raise debug 'relevant sql examples %', jsonb_pretty(_ctx_sql);
                return jsonb_build_object
                ( 'sql_statement', _answer
                , 'relevant_database_objects', _ctx_obj
                , 'relevant_sql_examples', _ctx_sql
                , 'iterations', (_max_iter - _iter_remaining)
                );
            end if;
        end loop;
        _iter_remaining = _iter_remaining - 1;
    end loop;
    return null;
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;
