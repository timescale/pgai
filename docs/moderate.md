# Moderate

Let's say you want to moderate comments using OpenAI. You can do it in two ways:

1. Using a trigger that will moderate the comment before it's inserted or updated in the database.
2. Using a background action that will moderate the comments every [N configurable] seconds.

## Via trigger

You can get the full example in the [trigger_moderate.sql](examples/trigger_moderate.sql) file.

First, let's create the extension and set the API key:

```sql
create extension if not exists ai cascade;
```

To set the API key, you can use the following command:
```sql
select set_config('ai.openai_api_key', :'OPENAI_API_KEY', false) is not null as set_config;
```

Or through PGOPTIONS in the command line:

```bash
PGOPTIONS="-c ai.openai_api_key=$OPENAI_API_KEY" psql -d "postgres://<username>:<password>@<host>:<port>/<database-name>"
```

So, let's create table to store the comments:

```sql
CREATE TABLE comments (
    id SERIAL PRIMARY KEY,
    body TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'pending'
);
```

Now, let's create a function that classifies the result of the openai API.

```sql
CREATE OR REPLACE FUNCTION get_moderation_status(result jsonb)
RETURNS TEXT AS $$
BEGIN
    IF result->>'flagged' IS NOT NULL THEN
        IF result->'categories'->>'violence' then
            return 'violence';
        END IF;
        IF result->'categories'->>'harassment' then
            return 'harassment';
        END IF;
        IF result->'categories'->>'hate' then
            return 'hate';
        END IF;
        IF result->'categories'->>'sexual' then
            return 'sexual';
        end if;
    end if;
    return 'approved';
end;
$$ language plpgsql;
```

Creating the trigger function that changes the status of the comment based on the result of the openai API.

```sql
CREATE OR REPLACE FUNCTION moderate_comment() RETURNS TRIGGER AS $$
declare
    out jsonb;
BEGIN
  select ai.openai_moderate(
    'text-moderation-stable',
    NEW.body,
     api_key=>current_setting('ai.openai_api_key', false) -- fail if setting not available
  )->'results'->0 into out;
  NEW.status = get_moderation_status(out);

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

Creating the trigger:

```sql
CREATE TRIGGER moderate_comment_trigger
BEFORE INSERT OR UPDATE ON comments
  FOR EACH ROW EXECUTE FUNCTION moderate_comment();
```

Testing the trigger:

```sql
insert into comments (body) values
  ('I love the new product'),
  ('He is an asshole'),
  ('I want to kill them all');
```

Checking the results:

```sql
table comments;
id |          body           |         created_at         |   status
----+-------------------------+----------------------------+------------
  1 | I love the new product  | 2024-06-07 19:07:10.884519 | approved
  2 | He is an asshole        | 2024-06-07 19:07:10.884519 | harassment
  3 | I want to kill them all | 2024-06-07 19:07:10.884519 | violence
```

## Via background action

Background options will not be blocking your transactions, so it's a better option for
moderating comments in a production environment and for a large number of comments.

Check out [background_actions.md](background_actions.md) for more information on
how to setup background actions to use open ai keys properly.

You can get the full example in the [bg_worker_moderate.sql](examples/bg_worker_moderate.sql).

For the background action, instead of the trigger, we will create a procedure
that will moderate the comments:

```sql
CREATE OR REPLACE FUNCTION get_moderation_status(body TEXT, api_key TEXT)
RETURNS TEXT AS $$
DECLARE
    result JSONB;
    category TEXT;
    api_key text;
BEGIN

    select current_setting('ai.openai_api_key', false) into api_key;
    -- Call OpenAI moderation endpoint
    select ai.openai_moderate('text-moderation-stable',
      body,
      api_key => api_key)->'results'->0 into result;

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
```

We'll also create a procedure that will moderate the comments:

```sql
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
```

and schedule the job to run every 5 seconds:

```sql
SELECT add_job('check_new_comments_to_moderate','5 seconds',
  config => format('{"api_key": "%s"}', :'OPENAI_API_KEY')::jsonb);
```

The testing can be very similar:

```sql
insert into comments (body) values
  ('I love the new product'),
  ('He is an asshole'),
  ('I want to kill them all');
```

If something does not work as expected, check out this query to filter out the error messages
from the job history from the last 10 minutes.

```sql
select err_message from timescaledb_information.job_history
where proc_name = 'check_new_comments_to_moderate'
and finish_time is not null
and finish_time > now() - interval '10 minutes';
```

