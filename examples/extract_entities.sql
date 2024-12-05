-- Extract entities example: https://github.com/anthropics/anthropic-cookbook/tree/main/tool_use
\getenv anthropic_api_key ANTHROPIC_API_KEY

CREATE OR REPLACE FUNCTION public.detect_entities(input_text text)
RETURNS TABLE(entity_name text, entity_type text, entity_context text)
AS $$
DECLARE
    api_response jsonb;
    entities_json jsonb;
BEGIN
    SELECT ai.anthropic_generate(
        'claude-3-5-sonnet-20240620',
        jsonb_build_array(
            jsonb_build_object(
                'role', 'user',
                'content', input_text
            )
        ),
        _max_tokens => 4096,
        _tools => jsonb_build_array(
            jsonb_build_object(
                'name', 'print_entities',
                'description', 'Prints extract named entities.',
                'input_schema', jsonb_build_object(
                    'type', 'object',
                    'properties', jsonb_build_object(
                        'entities', jsonb_build_object(
                            'type', 'array',
                            'items', jsonb_build_object(
                                'type', 'object',
                                'properties', jsonb_build_object(
                                    'name', jsonb_build_object('type', 'string', 'description', 'The extracted entity name.'),
                                    'type', jsonb_build_object('type', 'string', 'description', 'The entity type (e.g., PERSON, ORGANIZATION, LOCATION).'),
                                    'context', jsonb_build_object('type', 'string', 'description', 'The context in which the entity appears in the text.')
                                ),
                                'required', jsonb_build_array('name', 'type', 'context')
                            )
                        )
                    ),
                    'required', jsonb_build_array('entities')
                )
            )
        )
    ) INTO api_response;

    entities_json := jsonb_extract_path_text(api_response::jsonb, 'content', '1', 'input', 'entities')::jsonb;

    RETURN QUERY
    SELECT 
        e->>'name' AS entity_name,
        e->>'type' AS entity_type,
        e->>'context' AS entity_context
    FROM jsonb_array_elements(entities_json) AS e;

EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'An error occurred: %', SQLERRM;
        RAISE NOTICE 'API Response: %', api_response;
        RETURN;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.anonymize_text(input_text text)
RETURNS text
AS $$
DECLARE
    entity record;
    anonymized text := input_text;
BEGIN
    -- Replace entities with their types, starting with the longest entities
    FOR entity IN (
        SELECT entity_name, entity_type
        FROM public.detect_entities(input_text)
        ORDER BY length(entity_name) DESC
    )
    LOOP
        anonymized := regexp_replace(
            anonymized, 
            '\m' || regexp_replace(entity.entity_name, '([().\\*+?])', '\\\1', 'g') || '\M', 
            ':' || entity.entity_type || ':', 
            'gi'
        );
    END LOOP;

    RETURN anonymized;
END;
$$ LANGUAGE plpgsql;

