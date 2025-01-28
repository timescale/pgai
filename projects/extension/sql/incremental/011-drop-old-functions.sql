
-- adding `tools` and `response_format` parameters
drop function if exists ai.ollama_chat_complete(text, jsonb, text, text, jsonb);

-- changing type of `tool_choice` parameter
drop function if exists ai.openai_chat_complete(text, jsonb, text, text, text, float8, jsonb, boolean, int, int, int, float8, jsonb, int, text, float8, float8, jsonb, jsonb, text);