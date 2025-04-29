do language plpgsql $block$
DECLARE
    _vectorizer RECORD;
    _chunking jsonb;
    _chunk_column text;
    _config jsonb;
BEGIN
    -- Loop through all vectorizers
    FOR _vectorizer IN SELECT id, config FROM ai.vectorizer
    LOOP
        -- Extract the chunking config and chunk_column
        _chunking := _vectorizer.config operator(pg_catalog.->)'chunking';
        _chunk_column := _chunking operator(pg_catalog.->>)'chunk_column';
        
        IF _chunk_column IS NOT NULL THEN
            -- Create new config:
            -- 1. Add loading config
            -- 2. Add parsing config
            -- 3. Remove chunk_column from chunking config
            _config := _vectorizer.config operator(pg_catalog.||) jsonb_build_object(
                'loading', json_build_object(
                    'implementation', 'column',
                    'config_type', 'loading',
                    'column_name', _chunk_column,
                    'retries', 6
           ),
                'parsing', json_build_object(
                    'implementation', 'auto',
                    'config_type', 'parsing'
                ),
                'chunking', _chunking operator(pg_catalog.-) 'chunk_column',
                'version', '__version__'
            );
            
            -- Update the vectorizer with new config
            UPDATE ai.vectorizer 
            SET config = _config
            WHERE id operator(pg_catalog.=) _vectorizer.id;
        END IF;
    END LOOP;
end;
$block$;