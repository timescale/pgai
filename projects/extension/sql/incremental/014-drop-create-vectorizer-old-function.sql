-- adding a new jsonb param to include the loader.
drop function if exists ai.create_vectorizer(regclass,name,jsonb,jsonb,jsonb,jsonb,jsonb,jsonb,name,name,name,name,name,name,name[],boolean);
-- adding a new boolean chunk_document to infer if we're validating a chunker that relies on documents.
drop function if exists ai._validate_chunking(jsonb,name,name);
