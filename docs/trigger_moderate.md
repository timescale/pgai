# Trigger moderate

Let's say you want to moderate comments using OpenAI.

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
  select openai_moderate(
    'text-moderation-stable',
    NEW.body
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

