
create extension if not exists ai cascade;
create extension if not exists timescaledb;

-- setting a default id. Overwrite in the next step if the vectorizer has not been created.
\set vectorizer_id 1

-- create a vectorizer
select ai.create_vectorizer
( 'public.wiki'::regclass
, embedding=>ai.embedding_openai('text-embedding-3-small', 1536)
, chunking=>ai.chunking_recursive_character_text_splitter('body')
, formatting=>ai.formatting_python_template('title: $title $chunk')
, scheduling=>ai.scheduling_timescaledb
        ( interval '5m'
        , initial_start=>'2050-01-06'::timestamptz -- don't start it for a long time!
        , timezone=>'America/Chicago'
        )
, processing=>ai.processing_default
        ( batch_size=>20
        , concurrency=>1
        )
) as vectorizer_id
\gset

-- view the vectorizer row
select jsonb_pretty(to_jsonb(x))
from ai.vectorizer x
where x.id = :vectorizer_id
;

-- view the background job
select j.*
from timescaledb_information.jobs j
inner join ai.vectorizer x on (j.job_id = (x.config->'scheduling'->>'job_id')::int)
where x.id = :vectorizer_id
;

\set executor_url 'http://bastion-gateway.savannah-system.svc.cluster.local.:8080'
\set executor_events_path '/api/v1/events'

-- Overwrite if env vars are defined
\getenv executor_url EXECUTOR_URL
\getenv executor_events_path EXECUTOR_EVENTS_PATH

select set_config
( 'ai.external_function_executor_url'
, :'executor_url'
, false
);
select set_config
( 'ai.external_functions_executor_events_path'
, :'executor_events_path'
, false
);

-- how many items in the queue?
select ai.vectorizer_queue_pending(:vectorizer_id);

\getenv executor_disabled EXECUTOR_DISABLED
\if :{?executor_disabled}
        \echo 'Not calling the executor because EXECUTOR_DISABLED=true'
\else
        -- send the http request
        select ai.execute_vectorizer(:vectorizer_id);
\endif

-- how many items in the queue?
select ai.vectorizer_queue_pending(:vectorizer_id)
\watch 10
