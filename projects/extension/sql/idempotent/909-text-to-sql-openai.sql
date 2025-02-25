--FEATURE-FLAG: text_to_sql

-------------------------------------------------------------------------------
-- text_to_sql_openai
create or replace function ai.text_to_sql_openai
( model pg_catalog.text
, api_key pg_catalog.text default null
, api_key_name pg_catalog.text default null
, base_url pg_catalog.text default null
, frequency_penalty pg_catalog.float8 default null
, logit_bias pg_catalog.jsonb default null
, logprobs pg_catalog.bool default null
, top_logprobs pg_catalog.int4 default null
, max_tokens pg_catalog.int4 default null
, n pg_catalog.int4 default null
, presence_penalty pg_catalog.float8 default null
, seed pg_catalog.int4 default null
, stop pg_catalog.text default null
, temperature pg_catalog.float8 default null
, top_p pg_catalog.float8 default null
, openai_user pg_catalog.text default null
, max_iter pg_catalog.int2 default null
, max_results pg_catalog.int8 default null
, max_vector_dist pg_catalog.float8 default null
, obj_renderer pg_catalog.regprocedure default null
, sql_renderer pg_catalog.regprocedure default null
, user_prompt text default null
, system_prompt text default null
, include_entire_schema bool default null
, only_these_objects regclass[] default null
) returns pg_catalog.jsonb
as $func$
    select json_object
    ( 'provider': 'openai'
    , 'model': model
    , 'api_key': api_key
    , 'api_key_name': api_key_name
    , 'base_url': base_url
    , 'frequency_penalty': frequency_penalty
    , 'logit_bias': logit_bias
    , 'logprobs': logprobs
    , 'top_logprobs': top_logprobs
    , 'max_tokens': max_tokens
    , 'n': n
    , 'presence_penalty': presence_penalty
    , 'seed': seed
    , 'stop': stop
    , 'temperature': temperature
    , 'top_p': top_p
    , 'openai_user': openai_user
    , 'max_iter': max_iter
    , 'max_results': max_results
    , 'max_vector_dist': max_vector_dist
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
-- _text_to_sql_openai
create function ai._text_to_sql_openai
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
    _api_key text;
    _api_key_name text;
    _base_url text;
    _frequency_penalty float8;
    _logit_bias jsonb;
    _logprobs boolean;
    _top_logprobs int;
    _n int;
    _presence_penalty float8;
    _seed int;
    _stop text;
    _temperature float8;
    _top_p float8;
    _tools jsonb;
    _openai_user text;
    _system_prompt text;
    _questions jsonb = jsonb_build_array(question);
    _questions_embedded @extschema:vector@.vector[];
    _ctx_obj jsonb = jsonb_build_array();
    _ctx_sql jsonb = jsonb_build_array();
    _sql text;
    _samples jsonb = '{}';
    _samples_sql text;
    _prompt_obj_list text;
    _prompt_obj text;
    _prompt_sql text;
    _prompt_header text;
    _prompt text;
    _response jsonb;
    _message record;
    _tool_call record;
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
    _model = coalesce(_config->>'model', 'o3-mini');
    _api_key = _config operator(pg_catalog.->>) 'api_key';
    _api_key_name = _config operator(pg_catalog.->>) 'api_key_name';
    _base_url = _config operator(pg_catalog.->>) 'base_url';
    _frequency_penalty = (_config operator(pg_catalog.->>) 'frequency_penalty')::float8;
    _logit_bias = _config operator(pg_catalog.->) 'logit_bias';
    _logprobs = (_config operator(pg_catalog.->>) 'logprobs')::boolean;
    _top_logprobs = (_config operator(pg_catalog.->>) 'top_logprobs')::int4;
    _n = (_config operator(pg_catalog.->>) 'n')::int4;
    _presence_penalty = (_config operator(pg_catalog.->>) 'presence_penalty')::float8;
    _seed = (_config operator(pg_catalog.->>) 'seed')::int4;
    _stop = _config operator(pg_catalog.->>) 'stop';
    _temperature = (_config operator(pg_catalog.->>) 'temperature')::float8;
    _top_p = (_config operator(pg_catalog.->>) 'top_p')::float8;
    _openai_user = _config operator(pg_catalog.->>) 'openai_user';
    _system_prompt = coalesce
        ( _config->>'system_prompt'
        , pg_catalog.concat_ws
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
        , $$Use the "request_table_sample" tool if you need examples of the data in a table.$$
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

        -- render samples
        raise debug 'rendering table samples';
        select string_agg(value, E'\n\n')
        into strict _samples_sql
        from jsonb_each_text(_samples)
        ;

        -- render the user prompt
        raise debug 'rendering user prompt';
        _prompt = concat_ws
        ( E'\n'
        , _prompt_header
        , coalesce(_prompt_obj_list, '')
        , coalesce(_prompt_obj, '')
        , coalesce(_samples_sql, '')
        , coalesce(_prompt_sql, '')
        , coalesce(_prompt_err, '')
        , concat('Q: ', question)
        );
        raise debug '%', _prompt;

        -- tool definitions ---------------------------------------------------
        _tools = $json$
        [
            {
                "type": "function",
                "function": {
                    "name": "request_more_context_by_question",
                    "description": "Request additional database object descriptions by providing a focused question for semantic search. Use this when the current context is insufficient to generate a confident SQL query. Frame your question to target specific tables, relationships, or attributes needed.",
                    "parameters": {
                        "type": "object",
                        "properties" : {
                            "question": {
                                "type": "string",
                                "description": "A brief question (max 20 words) focused on a specific database structure or relationship. Avoid explaining reasoning or context."
                            }
                        },
                        "required": ["question"],
                        "additionalProperties": false
                    },
                    "strict": true
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "request_table_sample",
                    "description": "Request a sample of rows from a specified table or view to better understand its data patterns and content.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "The fully qualified `schema.name` of the table or view to sample. (e.g., 'schema_name.table_name')"
                            },
                            "total": {
                                "type": "integer",
                                "description": "The total number of rows to return in the sample, the max is 10."
                            }
                        },
                        "required": ["name", "total"],
                        "additionalProperties": false
                    },
                    "strict": true
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "answer_user_question_with_sql_statement",
                    "description": "Provide a SQL query that answers the user's question.",
                    "parameters": {
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
                        "required": ["sql_statement", "command_type", "relevant_database_object_ids", "relevant_sql_example_ids"],
                        "additionalProperties": false
                    },
                    "strict": true
                }
            }
        ]
        $json$::jsonb
        ;
        
        -- call llm -----------------------------------------------------------
        raise debug 'calling llm';
        select ai.openai_chat_complete
        ( _model
        , jsonb_build_array
          ( jsonb_build_object('role', 'system', 'content', _system_prompt)
          , jsonb_build_object('role', 'user', 'content', _prompt)
          )
        , tools=>_tools
        , tool_choice=>
            case when _iter_remaining = 0 then 
                -- force the LLM to provide an answer if we are out of iterations
                '{"type": "function", "function": {"name": "answer_user_question_with_sql_statement"}}'
            else 'required' -- must use one tool
            end
        , api_key=>_api_key
        , api_key_name=>_api_key_name
        , base_url=>_base_url
        , frequency_penalty=>_frequency_penalty
        , logit_bias=>_logit_bias
        , logprobs=>_logprobs
        , top_logprobs=>_top_logprobs
        , n=>_n
        , presence_penalty=>_presence_penalty
        , seed=>_seed
        , stop=>_stop
        , temperature=>_temperature
        , top_p=>_top_p
        , openai_user=>_openai_user
        ) into strict _response
        ;

        -- process the response -----------------------------------------------
        
        -- With tool_choice set to either required or a specific tool, we will only
        -- get one message per interaction, but I have coded this to handle multiple
        -- anyway in case that changes
        raise debug 'received % messages', jsonb_array_length(_response->'choices');
        <<message_loop>>
        for _message in
        (
            select
              (m->'index')::int4 as idx
            , jsonb_extract_path_text(m, 'message', 'content') as content
            , jsonb_extract_path_text(m, 'message', 'refusal') as refusal
            , jsonb_extract_path(m, 'message', 'tool_calls') as tool_calls
            from jsonb_array_elements(_response->'choices') m
        )
        loop
            if _message.content is not null then
                raise debug '%', _message.content;
            end if;
            if _message.refusal is not null then
                raise exception 'LLM refused to cooperate: %', _message.refusal;
            end if;
            
            -- At the moment, it appears we cannot both force the LLM to use at least one tool
            -- AND allow it to call multiple tools in the same interaction. Ideally, we could
            -- force it to use one or more tools in each interaction. I have coded the loop 
            -- below to be able to handle multiple tool calls even though we only get one at a
            -- time right now
            <<tool_call_loop>>
            for _tool_call in
            (
                select
                  t.id
                , t.type
                , t.function->>'name' as name
                , (t.function->>'arguments')::jsonb as arguments -- it's a string *containing* json :eyeroll:
                from jsonb_to_recordset(_message.tool_calls) t
                ( id text
                , type text
                , function jsonb
                )
            )
            loop
                case _tool_call.name
                    when 'request_more_context_by_question' then
                        raise debug 'tool use: request_more_context_by_question: %', _tool_call.arguments->'question';
                        -- append the question to the list of questions to use on the next iteration
                        select _questions || jsonb_build_array(_tool_call.arguments->'question')
                        into strict _questions
                        ;
                    when 'request_table_sample' then
                        raise debug 'tool use: request_table_sample: %', _tool_call.arguments;
                        select _samples || jsonb_build_object
                        ( _tool_call.arguments->>'name'
                        , ai.render_sample
                          ( (_tool_call.arguments->>'name')
                          , (_tool_call.arguments->>'total')::int4
                          , search_path
                          )
                        )
                        into strict _samples
                        ;
                    when 'answer_user_question_with_sql_statement' then
                        raise debug 'tool use: answer_user_question_with_sql_statement: %', _tool_call.arguments;
                        -- throw out any obj that the LLM did NOT mark as relevant
                        select jsonb_agg(r) into _ctx_obj
                        from jsonb_array_elements_text(_tool_call.arguments->'relevant_database_object_ids') i
                        inner join jsonb_to_recordset(_ctx_obj) r(id bigint, classid oid, objid oid)
                        on (i::bigint = r.id)
                        ;
                        -- throw out any sql that the LLM did NOT mark as relevant
                        select jsonb_agg(r) into _ctx_sql
                        from jsonb_array_elements_text(_tool_call.arguments->'relevant_sql_example_ids') i
                        inner join jsonb_to_recordset(_ctx_sql) r(id bigint, sql text, description text)
                        on (i::int = r.id)
                        ;
                        -- get the sql statement
                        select _tool_call.arguments->>'sql_statement' into strict _answer;
                        -- validate the sql statement if we can
                        select upper(_tool_call.arguments->>'command_type') into strict _command_type;
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
                                continue tool_call_loop;
                            end if;
                        end if;
                        -- we got a valid sql statement, or we got a sql statement for which we cannot
                        -- check the validity with EXPLAIN
                        exit main_loop;
                    else
                        raise warning 'invalid tool called for: %',  _tool_call.name;
                end case;
            end loop tool_call_loop;
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
