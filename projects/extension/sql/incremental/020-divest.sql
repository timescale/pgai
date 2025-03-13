
-------------------------------------------------------------------------------
-- schema
alter extension ai drop schema ai;
alter schema ai owner to pg_database_owner;

-------------------------------------------------------------------------------
-- tables, views, sequences
do $block$
declare
    _rec record;
    _sql text;
begin
    for _rec in
    (
        select
          n.nspname
        , k.relname
        , k.oid
        , k.relkind
        from pg_catalog.pg_depend d
        inner join pg_catalog.pg_class k on (d.objid = k.oid)
        inner join pg_catalog.pg_namespace n on (k.relnamespace = n.oid)
        inner join pg_catalog.pg_extension x on (d.refobjid = x.oid)
        where d.classid = 'pg_catalog.pg_class'::regclass::oid
        and d.refclassid = 'pg_catalog.pg_extension'::regclass::oid
        and d.deptype = 'e'
        and x.extname = 'ai'
        and (n.nspname, k.relname) not in
        (
            values
              ('ai', 'migration')
            , ('ai', 'feature_flag')
            , ('ai', '_secret_permissions')
            , ('ai', 'secret_permissions')
        )
    )
    loop
        select format
        ( $sql$alter extension ai drop %s %I.%I$sql$
        , case _rec.relkind
            when 'r' then 'table'
            when 'S' then 'sequence'
            when 'v' then 'view'
          end
        , _rec.nspname
        , _rec.relname
        ) into strict _sql
        ;
        raise notice '%', _sql;
        execute _sql;
        
        select format
        ( $sql$alter %s %I.%I owner to pg_database_owner$sql$
        , case _rec.relkind
            when 'r' then 'table'
            when 'S' then 'sequence'
            when 'v' then 'view'
          end
        , _rec.nspname
        , _rec.relname
        ) into strict _sql
        ;
        raise notice '%', _sql;
        execute _sql;
    end loop;
end;
$block$;
;


-------------------------------------------------------------------------------
-- triggers


-------------------------------------------------------------------------------
-- event triggers



-------------------------------------------------------------------------------
-- functions, procedures
do $block$
declare
    _rec record;
    _sql text;
begin
    for _rec in
    (
        select *
        from
        (
            select format
            ( $sql$%s %I.%I(%s)$sql$
            , p.prokind
            , n.nspname
            , p.proname
            , pg_catalog.pg_get_function_identity_arguments(p.oid)
            ) as spec
            , p.oid
            from pg_catalog.pg_depend d
            inner join pg_catalog.pg_proc p on (d.objid = p.oid)
            inner join pg_catalog.pg_namespace n on (p.pronamespace = n.oid)
            inner join pg_catalog.pg_extension x on (d.refobjid = x.oid)
            where d.classid = 'pg_catalog.pg_proc'::regclass::oid
            and d.refclassid = 'pg_catalog.pg_extension'::regclass::oid
            and d.deptype = 'e'
            and x.extname = 'ai'
        ) x
        where x.spec not in
        ( 'function ai.openai_tokenize(model text, text_input text)'
        , 'function ai.openai_detokenize(model text, tokens integer[])'
        , 'function ai.openai_list_models(api_key text, api_key_name text, extra_headers jsonb, extra_query jsonb, "verbose" boolean, client_config jsonb)'
        , 'function ai.openai_list_models_with_raw_response(api_key text, api_key_name text, extra_headers jsonb, extra_query jsonb, "verbose" boolean, client_config jsonb)'
        , 'function ai.openai_embed(model text, input_text text, api_key text, api_key_name text, dimensions integer, openai_user text, extra_headers jsonb, extra_query jsonb, extra_body jsonb, "verbose" boolean, client_config jsonb)'
        , 'function ai.openai_embed(model text, input_texts text[], api_key text, api_key_name text, dimensions integer, openai_user text, extra_headers jsonb, extra_query jsonb, extra_body jsonb, "verbose" boolean, client_config jsonb)'
        , 'function ai.openai_embed(model text, input_tokens integer[], api_key text, api_key_name text, dimensions integer, openai_user text, extra_headers jsonb, extra_query jsonb, extra_body jsonb, "verbose" boolean, client_config jsonb)'
        , 'function ai.openai_embed_with_raw_response(model text, input_text text, api_key text, api_key_name text, dimensions integer, openai_user text, extra_headers jsonb, extra_query jsonb, extra_body jsonb, "verbose" boolean, client_config jsonb)'
        , 'function ai.openai_embed_with_raw_response(model text, input_texts text[], api_key text, api_key_name text, dimensions integer, openai_user text, extra_headers jsonb, extra_query jsonb, extra_body jsonb, "verbose" boolean, client_config jsonb)'
        , 'function ai.openai_embed_with_raw_response(model text, input_tokens integer[], api_key text, api_key_name text, dimensions integer, openai_user text, extra_headers jsonb, extra_query jsonb, extra_body jsonb, "verbose" boolean, client_config jsonb)'
        , 'function ai.openai_chat_complete(model text, messages jsonb, api_key text, api_key_name text, frequency_penalty double precision, logit_bias jsonb, logprobs boolean, top_logprobs integer, max_tokens integer, max_completion_tokens integer, n integer, presence_penalty double precision, response_format jsonb, seed integer, stop text, temperature double precision, top_p double precision, tools jsonb, tool_choice text, openai_user text, extra_headers jsonb, extra_query jsonb, extra_body jsonb, "verbose" boolean, client_config jsonb)'
        , 'function ai.openai_chat_complete_with_raw_response(model text, messages jsonb, api_key text, api_key_name text, frequency_penalty double precision, logit_bias jsonb, logprobs boolean, top_logprobs integer, max_tokens integer, max_completion_tokens integer, n integer, presence_penalty double precision, response_format jsonb, seed integer, stop text, temperature double precision, top_p double precision, tools jsonb, tool_choice text, openai_user text, extra_headers jsonb, extra_query jsonb, extra_body jsonb, "verbose" boolean, client_config jsonb)'
        , 'function ai.openai_chat_complete_simple(message text, api_key text, api_key_name text, "verbose" boolean, client_config jsonb)'
        , 'function ai.openai_moderate(model text, input_text text, api_key text, api_key_name text, extra_headers jsonb, extra_query jsonb, extra_body jsonb, "verbose" boolean, client_config jsonb)'
        , 'function ai.openai_moderate_with_raw_response(model text, input_text text, api_key text, api_key_name text, extra_headers jsonb, extra_query jsonb, extra_body jsonb, "verbose" boolean, client_config jsonb)'
        , 'function ai.openai_client_config(base_url text, timeout_seconds double precision, organization text, project text, max_retries integer, default_headers jsonb, default_query jsonb)'
        , 'function ai.ollama_list_models(host text, "verbose" boolean)'
        , 'function ai.ollama_ps(host text, "verbose" boolean)'
        , 'function ai.ollama_embed(model text, input_text text, host text, keep_alive text, embedding_options jsonb, "verbose" boolean)'
        , 'function ai.ollama_generate(model text, prompt text, host text, images bytea[], keep_alive text, embedding_options jsonb, system_prompt text, template text, context integer[], "verbose" boolean)'
        , 'function ai.ollama_chat_complete(model text, messages jsonb, host text, keep_alive text, chat_options jsonb, tools jsonb, response_format jsonb, "verbose" boolean)'
        , 'function ai.anthropic_list_models(api_key text, api_key_name text, base_url text, "verbose" boolean)'
        , 'function ai.anthropic_generate(model text, messages jsonb, max_tokens integer, api_key text, api_key_name text, base_url text, timeout double precision, max_retries integer, system_prompt text, user_id text, stop_sequences text[], temperature double precision, tool_choice jsonb, tools jsonb, top_k integer, top_p double precision, "verbose" boolean)'
        , 'function ai.cohere_list_models(api_key text, api_key_name text, endpoint text, default_only boolean, "verbose" boolean)'
        , 'function ai.cohere_tokenize(model text, text_input text, api_key text, api_key_name text, "verbose" boolean)'
        , 'function ai.cohere_detokenize(model text, tokens integer[], api_key text, api_key_name text, "verbose" boolean)'
        , 'function ai.cohere_embed(model text, input_text text, api_key text, api_key_name text, input_type text, truncate_long_inputs text, "verbose" boolean)'
        , 'function ai.cohere_classify(model text, inputs text[], api_key text, api_key_name text, examples jsonb, truncate_long_inputs text, "verbose" boolean)'
        , 'function ai.cohere_classify_simple(model text, inputs text[], api_key text, api_key_name text, examples jsonb, truncate_long_inputs text, "verbose" boolean)'
        , 'function ai.cohere_rerank(model text, query text, documents text[], api_key text, api_key_name text, top_n integer, max_tokens_per_doc integer, "verbose" boolean)'
        , 'function ai.cohere_rerank_simple(model text, query text, documents text[], api_key text, api_key_name text, top_n integer, max_tokens_per_doc integer, "verbose" boolean)'
        , 'function ai.cohere_chat_complete(model text, messages jsonb, api_key text, api_key_name text, tools jsonb, documents jsonb, citation_options jsonb, response_format jsonb, safety_mode text, max_tokens integer, stop_sequences text[], temperature double precision, seed integer, frequency_penalty double precision, presence_penalty double precision, k integer, p double precision, logprobs boolean, tool_choice text, strict_tools boolean, "verbose" boolean)'
        , 'function ai.reveal_secret(secret_name text, use_cache boolean)'
        , 'function ai.grant_secret(secret_name text, grant_to_role text)'
        , 'function ai.revoke_secret(secret_name text, revoke_from_role text)'
        , 'function ai.voyageai_embed(model text, input_text text, input_type text, api_key text, api_key_name text, "verbose" boolean)'
        , 'function ai.voyageai_embed(model text, input_texts text[], input_type text, api_key text, api_key_name text, "verbose" boolean)'
        , 'procedure ai.load_dataset_multi_txn(IN name text, IN config_name text, IN split text, IN schema_name name, IN table_name name, IN if_table_exists text, IN field_types jsonb, IN batch_size integer, IN max_batches integer, IN commit_every_n_batches integer, IN kwargs jsonb)'
        , 'function ai.load_dataset(name text, config_name text, split text, schema_name name, table_name name, if_table_exists text, field_types jsonb, batch_size integer, max_batches integer, kwargs jsonb)'
        , 'function ai.litellm_embed(model text, input_text text, api_key text, api_key_name text, extra_options jsonb, "verbose" boolean)'
        , 'function ai.litellm_embed(model text, input_texts text[], api_key text, api_key_name text, extra_options jsonb, "verbose" boolean)'
        , 'function ai.chunk_text(input text, chunk_size integer, chunk_overlap integer, separator text, is_separator_regex boolean)'
        , 'function ai.chunk_text_recursively(input text, chunk_size integer, chunk_overlap integer, separators text[], is_separator_regex boolean)'
        , 'function ai.grant_ai_usage(to_user name, admin boolean)'
        )
    )
    loop
        select format
        ( $sql$alter extension ai drop %s$sql$
        , _rec.spec
        ) into strict _sql
        ;
        raise notice '%', _sql;
        execute _sql;
        
        select format
        ( $sql$alter %s owner to pg_database_owner$sql$
        , _rec.spec
        ) into strict _sql
        ;
        raise notice '%', _sql;
        execute _sql;
    end loop;
end;
$block$;
;
