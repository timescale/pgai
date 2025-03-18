ALTER TABLE ai.vectorizer 
  ALTER COLUMN target_schema DROP NOT NULL,
  ALTER COLUMN target_table DROP NOT NULL,
  ALTER COLUMN view_schema DROP NOT NULL,
  ALTER COLUMN view_name DROP NOT NULL;
                              
-- Drop the existing unique constraint that includes target_schema and target_table
ALTER TABLE ai.vectorizer
  DROP CONSTRAINT vectorizer_target_schema_target_table_key;

-- Add a new unique constraint that only applies when both fields are not null
CREATE UNIQUE INDEX vectorizer_target_schema_target_table_idx
ON ai.vectorizer (target_schema, target_table)
WHERE target_schema IS NOT NULL AND target_table IS NOT NULL;

-- drop the old create_vectorizer and create_trigger function
DROP FUNCTION IF EXISTS ai._vectorizer_build_trigger_definition(name,name,name,name,jsonb);
DROP FUNCTION IF EXISTS ai.create_vectorizer(regclass,name,jsonb,jsonb,jsonb,jsonb,jsonb,jsonb,name,name,name,name,name,name,name[],boolean);

do language plpgsql $block$
DECLARE
    _vectorizer RECORD;
    _config jsonb;
BEGIN
    -- Loop through all vectorizers
    FOR _vectorizer IN SELECT id, config FROM ai.vectorizer
    LOOP
        -- add embedding column and skip_chunking flag to the config
        _config := _vectorizer.config operator(pg_catalog.||) jsonb_build_object(
            'embedding_column', 'embedding',
            'skip_chunking', false
        );

        -- Update the vectorizer with new config
        UPDATE ai.vectorizer 
        SET config = _config
        WHERE id operator(pg_catalog.=) _vectorizer.id;
    END LOOP;
end;
$block$;