do language plpgsql $block$
DECLARE
    _vectorizer RECORD;
    _constraint_name text;
    _sql text;
BEGIN
    -- Loop through all vectorizers
    FOR _vectorizer IN 
        SELECT 
            v.id,
            v.target_schema,
            v.target_table,
            v.source_schema,
            v.source_table
        FROM ai.vectorizer v
    LOOP
        -- Find the foreign key constraint for this vectorizer's store table
        SELECT conname INTO _constraint_name
        FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        JOIN pg_namespace n ON t.relnamespace = n.oid
        JOIN pg_class t2 ON c.confrelid = t2.oid
        JOIN pg_namespace n2 ON t2.relnamespace = n2.oid
        WHERE n.nspname = _vectorizer.target_schema
        AND t.relname = _vectorizer.target_table
        AND n2.nspname = _vectorizer.source_schema
        AND t2.relname = _vectorizer.source_table
        AND c.contype = 'f';

        IF _constraint_name IS NOT NULL THEN
            -- Build and execute the ALTER TABLE command to drop the constraint
            _sql := format(
                'ALTER TABLE %I.%I DROP CONSTRAINT %I',
                _vectorizer.target_schema,
                _vectorizer.target_table,
                _constraint_name
            );
            
            RAISE NOTICE 'Dropping foreign key constraint % from %.%', 
                _constraint_name, 
                _vectorizer.target_schema, 
                _vectorizer.target_table;
            
            EXECUTE _sql;
        ELSE
            RAISE NOTICE 'No foreign key constraint found for %.%', 
                _vectorizer.target_schema, 
                _vectorizer.target_table;
        END IF;
    END LOOP;
END;
$block$;

-- dropping in favour of new signatures
drop function if exists ai._vectorizer_create_source_trigger(name,name,name,name,name,jsonb);
drop function if exists ai._vectorizer_create_target_table(name,name,jsonb,name,name,integer,name[]);