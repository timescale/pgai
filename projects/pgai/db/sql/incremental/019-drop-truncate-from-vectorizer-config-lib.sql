-- in the extension, this was done in 009-drop-truncate-from-vectorizer-config.sql
-- but that has a mix of extension and vectorizer config changes.
-- so we need to split it out. but put it at the beginning of the lib changes.
-- since it's idempotent and no changes from 009-018 depend on it, the change in order is OK.
UPDATE ai.vectorizer SET config = config #- '{"embedding", "truncate"}' WHERE config @? '$.embedding.truncate';
