drop function if exists ai.openai_list_models(text, text, text);
drop function if exists ai.openai_embed(text, text, text, text, text, int, text);
drop function if exists ai.openai_embed(text, text [], text, text, text, int, text);
drop function if exists ai.openai_embed(text, int [], text, text, text, int, text);
drop function if exists ai.openai_chat_complete(
    text,
    jsonb,
    text,
    text,
    text,
    float8,
    jsonb,
    boolean,
    int,
    int,
    int,
    float8,
    jsonb,
    int,
    text,
    float8,
    float8,
    jsonb,
    text,
    text
);
drop function if exists ai.openai_moderate(text, text, text, text, text);
drop function if exists ai.openai_chat_complete_simple(text, text, text);
