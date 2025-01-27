
-- adding `tools` and `response_format` parameters
drop function if exists ai.ollama_chat_complete(text, jsonb, text, text, jsonb);
