
-- dropping in favour of the new signature (adding base_url param)
drop function if exists ai.embedding_openai(text,integer,text,text);