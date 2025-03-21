UPDATE ai.vectorizer SET config = config #- '{"embedding", "truncate"}' WHERE config @? '$.embedding.truncate';
