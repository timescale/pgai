do language plpgsql $block$
DECLARE
    _vectorizer RECORD;
    _function_body text;
    _pk_cols text;
    _sql text;
BEGIN
    -- Loop through all vectorizers
    FOR _vectorizer IN 
        SELECT 
            v.id,
            v.target_schema,
            v.target_table,
            v.source_schema,
            v.source_table,
            v.queue_schema,
            v.queue_table,
            v.trigger_name,
            v.source_pk
        FROM ai.vectorizer v
    LOOP
        -- Get the PK columns for the WHERE clause
        SELECT pg_catalog.string_agg(
            pg_catalog.format('%I = $1.%I', x.attname, x.attname),
            ' AND ' 
            order by x.pknum
        )
        INTO STRICT _pk_cols
        FROM pg_catalog.jsonb_to_recordset(_vectorizer.source_pk) x(pknum int, attname name);

        -- Drop the old trigger
        EXECUTE format(
            'DROP TRIGGER IF EXISTS %I ON %I.%I',
            _vectorizer.trigger_name,
            _vectorizer.source_schema,
            _vectorizer.source_table
        );

        -- Drop the old trigger function
        EXECUTE format(
            'DROP FUNCTION IF EXISTS %I.%I()',
            _vectorizer.queue_schema,
            _vectorizer.trigger_name
        );

        -- Create the new trigger function with updated logic
        SELECT format(
            $sql$
            CREATE FUNCTION %I.%I() RETURNS trigger
            AS $trg$
            BEGIN
                IF (TG_OP = 'DELETE') THEN
                    -- Delete all chunks in target table related to this row
                    EXECUTE pg_catalog.format(
                        'DELETE FROM %I.%I WHERE %s',
                        %L, %L, %L
                    ) USING OLD;
                    RETURN OLD;
                ELSIF (TG_OP = 'UPDATE') THEN
                    -- If PK has changed, delete old chunks and queue the new row
                    IF %s THEN
                        -- Delete old chunks
                        EXECUTE pg_catalog.format(
                            'DELETE FROM %I.%I WHERE %s',
                            %L, %L, %L
                        ) USING OLD;
                        
                        -- Queue the new row for processing
                        INSERT INTO %I.%I (%s)
                        VALUES (%s);
                    ELSE
                        -- If only non-PK columns changed, just queue the new row
                        INSERT INTO %I.%I (%s)
                        VALUES (%s);
                    END IF;
                    RETURN NEW;
                ELSIF (TG_OP = 'INSERT') THEN
                    -- Queue the new row
                    INSERT INTO %I.%I (%s)
                    VALUES (%s);
                    RETURN NEW;
                END IF;
                RETURN NULL;
            END;
            $trg$ LANGUAGE plpgsql VOLATILE PARALLEL SAFE SECURITY DEFINER
            SET search_path = pg_catalog, pg_temp;
            $sql$,
            _vectorizer.queue_schema, 
            _vectorizer.trigger_name,
            -- Parameters for the dynamic delete query
            _vectorizer.target_schema, 
            _vectorizer.target_table, 
            _pk_cols,
            -- PK change detection condition
            (
                SELECT pg_catalog.string_agg(
                    pg_catalog.format('OLD.%I IS DISTINCT FROM NEW.%I', x.attname, x.attname),
                    ' OR ' 
                    ORDER BY x.pknum
                )
                FROM pg_catalog.jsonb_to_recordset(_vectorizer.source_pk) x(pknum int, attname name)
            ),
            -- Target params for second delete
            _vectorizer.target_schema, 
            _vectorizer.target_table, 
            _pk_cols,
            -- Queue table parameters for PK change insert
            _vectorizer.queue_schema,
            _vectorizer.queue_table,
            (
                SELECT pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' ORDER BY x.attnum)
                FROM pg_catalog.jsonb_to_recordset(_vectorizer.source_pk) x(attnum int, attname name)
            ),
            (
                SELECT pg_catalog.string_agg(pg_catalog.format('NEW.%I', x.attname), ', ' ORDER BY x.attnum)
                FROM pg_catalog.jsonb_to_recordset(_vectorizer.source_pk) x(attnum int, attname name)
            ),
            -- Queue table parameters for normal update insert
            _vectorizer.queue_schema,
            _vectorizer.queue_table,
            (
                SELECT pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' ORDER BY x.attnum)
                FROM pg_catalog.jsonb_to_recordset(_vectorizer.source_pk) x(attnum int, attname name)
            ),
            (
                SELECT pg_catalog.string_agg(pg_catalog.format('NEW.%I', x.attname), ', ' ORDER BY x.attnum)
                FROM pg_catalog.jsonb_to_recordset(_vectorizer.source_pk) x(attnum int, attname name)
            ),
            -- Queue table parameters for insert
            _vectorizer.queue_schema,
            _vectorizer.queue_table,
            (
                SELECT pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' ORDER BY x.attnum)
                FROM pg_catalog.jsonb_to_recordset(_vectorizer.source_pk) x(attnum int, attname name)
            ),
            (
                SELECT pg_catalog.string_agg(pg_catalog.format('NEW.%I', x.attname), ', ' ORDER BY x.attnum)
                FROM pg_catalog.jsonb_to_recordset(_vectorizer.source_pk) x(attnum int, attname name)
            )
        ) INTO _sql;

        -- Create the new trigger function
        EXECUTE _sql;

        -- Revoke all on trigger function from public
        EXECUTE format(
            'REVOKE ALL ON FUNCTION %I.%I() FROM PUBLIC',
            _vectorizer.queue_schema,
            _vectorizer.trigger_name
        );

        -- Create the new trigger
        EXECUTE format(
            'CREATE TRIGGER %I AFTER INSERT OR UPDATE OR DELETE ON %I.%I FOR EACH ROW EXECUTE FUNCTION %I.%I()',
            _vectorizer.trigger_name,
            _vectorizer.source_schema,
            _vectorizer.source_table,
            _vectorizer.queue_schema,
            _vectorizer.trigger_name
        );
        
        RAISE NOTICE 'Updated trigger % for vectorizer %', _vectorizer.trigger_name, _vectorizer.id;
    END LOOP;
END;
$block$;