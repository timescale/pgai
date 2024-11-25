drop function if exists ai.ollama_embed(text, text, text, float8, jsonb);
drop function if exists ai.ollama_generate(text, text, text, bytea[], float8, jsonb, text, text, int[]);
drop function if exists ai.ollama_chat_complete(text, jsonb, text, float8, jsonb);
