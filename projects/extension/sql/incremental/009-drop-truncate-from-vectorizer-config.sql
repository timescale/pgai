DROP FUNCTION IF EXISTS ai.embedding_ollama(text,integer,text,boolean,jsonb,text);
DROP FUNCTION IF EXISTS ai.embedding_voyageai(text,integer,text,booleab,jsonb,text);
DROP FUNCTION IF EXISTS ai.voyageai_embed(text,text,text,boolean,text,text);
DROP FUNCTION IF EXISTS ai.voyageai_embed(text,text[],text,boolean,text,text);

UPDATE ai.vectorizer SET config = config #- '{"embedding", "truncate"}' WHERE config @? '$.embedding.truncate';
