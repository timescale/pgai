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
, include_entire_schema bool default null
, only_these_objects regclass[] default null
) returns pg_catalog.jsonb
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
    , 'include_entire_schema': include_entire_schema
    , 'only_these_objects': only_these_objects
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
, search_path text default pg_catalog.current_setting('search_path', true)
) returns jsonb
as $func$
declare
    _config jsonb = config;
    _catalog_name text = catalog_name;
    _max_iter int2;
    _iter int2;
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
    _samples_sql text;
    _prompt_obj_list text;
    _prompt_header text;
    _prompt text;
    _system_prompt text;
    _tools jsonb;
    _response jsonb;
    _message record;
    _answer text;
    _command_type text;
    _answer_valid bool;
    _err_msg text;
    _query_plan jsonb;
    _prompt_err text = '';
    _include_entire_schema bool;
    _only_these_objects regclass[];
begin
    -- initialize variables ---------------------------------------------------

    -- if a config was provided, use the settings available. defaults where missing
    -- if no config provided, use defaults for everything
    _max_iter = coalesce((_config->>'max_iter')::int2, 10);
    _iter_remaining = _max_iter;
    _max_results = coalesce((_config->>'max_results')::int8, 5);
    _max_vector_dist = (_config->>'max_vector_dist')::float8;
    _obj_renderer = coalesce((_config->>'obj_renderer')::pg_catalog.regprocedure, 'ai.render_semantic_catalog_obj(bigint, oid, oid)'::pg_catalog.regprocedure);
    _sql_renderer = coalesce((_config->>'sql_renderer')::pg_catalog.regprocedure, 'ai.render_semantic_catalog_sql(bigint, text, text)'::pg_catalog.regprocedure);
    _model = coalesce(_config->>'model', 'claude-3-7-sonnet-latest');
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
        , $$Do not add aliases to columns unless it is required syntactically.$$
        , $$If enough context has been provided to confidently address the question, use the "answer_user_question_with_sql_statement" tool to record your final answer in the form of a valid SQL statement.$$
        , coalesce(_config operator(pg_catalog.->>) 'user_prompt', '')
        );
    _include_entire_schema = coalesce((_config->>'include_entire_schema')::bool, false);
    
    select array_agg(to_regclass(x)) filter (where to_regclass(x) is not null) into _only_these_objects
    from jsonb_array_elements_text(_config->'only_these_objects') x
    ;
    if array_length(_only_these_objects, 1) = 0 then
        _only_these_objects = null;
    end if;

    -- get a list of commonly relevant database object names
    _prompt_obj_list = ai.render_semantic_catalog_obj_listing(20);
    
    -- main loop --------------------------------------------------------------
    
    -- Each iteration of the main loop sends one message to the LLM and processes
    -- the response. We do this until the LLM calls a tool to indicate that it has
    -- a final answer OR we have run _max_iter iterations.
    <<main_loop>>
    for _iter in 1.._max_iter loop
        raise debug 'iteration: %', _iter;
        _iter_remaining = _max_iter - _iter;

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
        case
            when _include_entire_schema then
                -- all the top-level objects
                raise debug 'including entire schema';
                select jsonb_agg
                ( jsonb_build_object
                  ( 'id', o.id
                  , 'classid', o.classid
                  , 'objid', o.objid
                  )
                  order by o.id
                ) into _ctx_obj
                from ai.semantic_catalog_obj o
                where o.objsubid = 0 -- top level objects only
                ;
            when _only_these_objects is not null then
                -- just the top-level objects specifically requested
                raise debug 'including only % specific objects', array_length(_only_these_objects, 1);
                select jsonb_agg
                ( jsonb_build_object
                  ( 'id', o.id
                  , 'classid', o.classid
                  , 'objid', o.objid
                  )
                  order by o.id
                ) into _ctx_obj
                from unnest(_only_these_objects) r
                inner join ai.semantic_catalog_obj o 
                on (o.objsubid = 0 -- top level objects only
                and o.classid = 'pg_catalog.pg_class'::regclass::oid
                and o.objid = r::oid
                )
                ;
            when jsonb_array_length(_questions) > 0 then
                -- semantic search for objects
                raise debug 'searching for database objects';
                select jsonb_agg(to_jsonb(x))
                into _ctx_obj
                from
                (
                    -- search for relevant objects
                    -- if a column matches, we want to render the whole table/view, so discard the objsubid
                    -- semantic search
                    select distinct x.id, x.classid, x.objid
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
                    from jsonb_to_recordset(_ctx_obj) r(id int8, classid oid, objid oid)
                ) x
                ;
                raise debug 'search found % database objects', jsonb_array_length(_ctx_obj);
            else
                -- noop
        end case;

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
        , coalesce(_prompt_err, '')
        , concat('Q: ', question)
        );
        raise debug '%', _prompt;

        -- call llm -----------------------------------------------------------
        _tools = $json$
        [
            {
                "name": "request_more_context_by_question",
                "description": "Request additional database object descriptions by providing a focused question for semantic search. Use this when the current context is insufficient to generate a confident SQL query. Frame your question to target specific tables, relationships, or attributes needed.",
                "input_schema": {
                    "type": "object",
                    "properties" : {
                        "question": {
                            "type": "string",
                            "description": "A brief question (max 20 words) focused on a specific database structure or relationship. Avoid explaining reasoning or context."
                        }
                    },
                    "required": ["question"]
                }
            },
            {
                "name": "answer_user_question_with_sql_statement",
                "description": "Provide a SQL query that answers the user's question.",
                "input_schema": {
                    "type": "object",
                    "properties" : {
                        "sql_statement": {
                            "type": "string",
                            "description": "A valid PostgreSQL SQL statement that addresses the user's question."
                        },
                        "command_type": {
                            "type": "string",
                            "description": "Indicate the type of SQL command used in the sql_statement. (e.g. 'SELECT', 'INSERT', 'UPDATE', or 'DELETE')"
                        },
                        "relevant_database_object_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "IDs of database objects used in constructing the answer."
                        },
                        "relevant_sql_example_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "IDs of SQL examples referenced in constructing the answer."
                        }
                    },
                    "required": ["sql_statement", "command_type", "relevant_database_object_ids", "relevant_sql_example_ids"]
                }
            }
        ]
        $json$::jsonb
        ;
        
        -- call llm -----------------------------------------------------------
        raise debug 'calling llm';
        select ai.anthropic_generate
        ( _model
        , jsonb_build_array(jsonb_build_object('role', 'user', 'content', _prompt))
        , system_prompt=>_system_prompt
        , tools=>_tools
        , tool_choice=>
          (
            case when _iter_remaining = 0 then
                -- force the LLM to provide an answer if we are out of iterations
                '{"type": "tool", "name": "answer_user_question_with_sql_statement"}'
            else '{"type": "any"}' -- must use at least one tool
            end
          )::jsonb
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
        <<message_loop>>
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
                            -- validate the sql statement if we can
                            select upper(_message.input->>'command_type') into _command_type;
                            if _command_type in ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'MERGE', 'VALUES') then
                                select
                                  x.valid
                                , x.err_msg
                                , x.query_plan
                                into
                                  _answer_valid
                                , _err_msg
                                , _query_plan
                                from ai._text_to_sql_explain(_answer, search_path=>search_path) x
                                ;
                                if not _answer_valid then
                                    -- render invalid sql statements
                                    _prompt_err = concat_ws
                                    ( E'\n'
                                    , _prompt_err -- keep prior bad queries. append new ones
                                    , '<invalid-sql-statement>'
                                    , concat_ws
                                      ( E'\n'
                                      , '/*'
                                      , '-- The following SQL statement is invalid. Fix this SQL or generate a new, valid SQL statement.'
                                      , '-- ONLY use database elements that have been described to you unless they are built-in to Postgres.'
                                      , _err_msg
                                      , '*/'
                                      )
                                    , _answer
                                    , '</invalid-sql-statement>'
                                    );
                                    -- we got a bad sql statement. continue processing and give the LLM
                                    -- another try unless we've hit _max_iter iterations
                                    continue message_loop;
                                end if;
                            end if;
                            -- we got a valid sql statement, or we got a sql statement for which we cannot
                            -- check the validity with EXPLAIN
                            exit main_loop;
                        else
                            raise warning 'invalid tool called for: %', _message.name;
                    end case;
            end case;
        end loop message_loop;
    end loop main_loop;
    
    -- return our results -----------------------------------------------------
    -- some elements may be null
    return jsonb_build_object
    ( 'sql_statement', _answer
    , 'command_type', _command_type
    , 'relevant_database_objects', _ctx_obj
    , 'relevant_sql_examples', _ctx_sql
    , 'iterations', (_max_iter - _iter_remaining)
    , 'query_plan', _query_plan
    , 'est_cost', jsonb_extract_path(_query_plan, '0', 'Plan', 'Total Cost')
    , 'est_rows', jsonb_extract_path(_query_plan, '0', 'Plan', 'Plan Rows')
    );
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;
