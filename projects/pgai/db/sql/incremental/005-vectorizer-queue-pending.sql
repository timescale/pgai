
-- we added a new parameter which changes the signature producing a new function
-- drop the old function if it exists from a prior extension version
-- we cascade drop because the ai.vectorizer_status view depends on this function
-- we'll immediate recreate the view, so we should be good
drop function if exists ai.vectorizer_queue_pending(int) cascade;
