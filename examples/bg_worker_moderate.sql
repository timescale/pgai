create extension if not exists ai cascade;
select set_config('ai.openai_api_key', :'OPENAI_API_KEY', false) is not null as set_config;

DROP TABLE IF EXISTS comments CASCADE;
CREATE TABLE comments (
    id SERIAL PRIMARY KEY,
    body TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'pending'
);

CREATE OR REPLACE FUNCTION get_moderation_status(body TEXT, api_key TEXT)
RETURNS TEXT AS $$
DECLARE
    result JSONB;
    category TEXT;
BEGIN
    -- Call OpenAI moderation endpoint
    select ai.openai_moderate( 'text-moderation-stable', body, api_key)->'results'->0 into result;

    -- Check if any category is flagged
    IF result->>'flagged' = 'true' THEN
        FOR category IN SELECT jsonb_object_keys(result->'categories') LOOP
            IF (result->'categories'->>category)::BOOLEAN THEN
                RETURN category;
            END IF;
        END LOOP;
    END IF;

    RETURN 'approved';
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE PROCEDURE check_new_comments_to_moderate(job_id int, config jsonb) LANGUAGE PLPGSQL AS
$$
declare
  comment record;
  api_key text;
BEGIN
  RAISE NOTICE 'Executing action % with config %', job_id, config;
  -- iterate over comments and moderate them
  api_key := config->>'api_key';
  for comment in select * from comments where status = 'pending' limit 1 for update skip locked loop
    update comments set status = get_moderation_status(comment.body, api_key)
    where id = comment.id;
  end loop;
END
$$;

SELECT add_job('check_new_comments_to_moderate','5 seconds',
  config => format('{"api_key": "%s"}', :'OPENAI_API_KEY')::jsonb);

insert into comments (body) values
  ('I love the new product'),
  ('He is an asshole'),
  ('I want to kill them all');

select pg_sleep(10);

table comments;

select err_message from timescaledb_information.job_history
where proc_name = 'check_new_comments_to_moderate'
and finish_time is not null
and finish_time > now() - interval '10 seconds';

\watch
