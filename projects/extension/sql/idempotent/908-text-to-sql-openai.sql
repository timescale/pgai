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
    _prompt_obj text;
    _prompt_sql text;
    _prompt_header text;
    _prompt text;
    _response jsonb;
    _message record;
    _tool_call record;
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
        , $$If enough context has been provided to confidently address the question, use the "answer_user_question_with_sql_statement" tool to record your final answer in the form of a valid SQL statement.$$
        , coalesce(_config operator(pg_catalog.->>) 'user_prompt', '')
        );

    while _iter_remaining > 0 loop
        raise debug 'iteration: %', (_max_iter - _iter_remaining + 1);
        _iter_remaining = _iter_remaining - 1;
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
                                "minimum": 1,
                                "maximum": 100,
                                "default": 10,
                                "description": "The total number of rows to return in the sample, the max is 10."
                            }
                        },
                        "required": ["name", "total"]
                    }
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
                        "required": ["sql_statement", "relevant_database_object_ids", "relevant_sql_example_ids"],
                        "additionalProperties": false
                    },
                    "strict": true
                }
            }
        ]
        $json$::jsonb
        ;

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
            '{"type": "function", "function": {"name": "answer_user_question_with_sql_statement"}}'
            else 'required'
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
        raise debug 'received % messages', jsonb_array_length(_response->'choices');
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
                raise debug '%', _message.refusal;
                -- TODO: continue? raise exception? i dunno
            end if;
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
                        select _tool_call.arguments->>'sql_statement' into strict _answer;
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
                        return jsonb_build_object
                        ( 'sql_statement', _answer
                        , 'relevant_database_objects', _ctx_obj
                        , 'relevant_sql_examples', _ctx_sql
                        , 'iterations', (_max_iter - _iter_remaining)
                        );
                end case
                ;
            end loop;
        end loop;
    end loop;
    return null;
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;
