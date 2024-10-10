create extension if not exists ai cascade;
select set_config('ai.openai_api_key', :'OPENAI_API_KEY', false) is not null as set_config;

DROP TABLE IF EXISTS comments CASCADE;
CREATE TABLE comments (
    id SERIAL PRIMARY KEY,
    body TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'pending'
);

create or replace function get_moderation_status(result jsonb)
returns text as $$
begin
    if result->>'flagged' is not null then
        if result->'categories'->>'violence' then
            return 'violence';
        end if;
        if result->'categories'->>'harassment' then
            return 'harassment';
        end if;
        if result->'categories'->>'hate' then
            return 'hate';
        end if;
        if result->'categories'->>'sexual' then
            return 'sexual';
        end if;
    end if;
    return 'approved';
end;
$$ language plpgsql;

CREATE OR REPLACE FUNCTION moderate_comment() RETURNS TRIGGER AS $$
declare
    out jsonb;
BEGIN
  select ai.openai_moderate(
    'text-moderation-stable',
    NEW.body
  )->'results'->0 into out;
  NEW.status = get_moderation_status(out);

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER moderate_comment_trigger
BEFORE INSERT OR UPDATE ON comments
  FOR EACH ROW EXECUTE FUNCTION moderate_comment();

-- testing

insert into comments (body) values
  ('I love the new product'),
  ('He is an asshole'),
  ('I want to kill them all');

table comments;
