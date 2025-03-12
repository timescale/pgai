CREATE OR REPLACE FUNCTION ai._worker_start(version text, expected_heartbeat_interval interval) RETURNS uuid AS $$
DECLARE
    worker_id uuid;
BEGIN
    --can add version check here
    INSERT INTO ai.vectorizer_worker_process (version, expected_heartbeat_interval) VALUES (version, expected_heartbeat_interval) RETURNING id INTO worker_id;
    RETURN worker_id;
END;
$$ LANGUAGE plpgsql security invoker
set search_path to pg_catalog, pg_temp;

CREATE OR REPLACE FUNCTION ai._worker_heartbeat(worker_id uuid, num_successes_since_last_heartbeat int, num_errors_since_last_heartbeat int, error_message text) RETURNS void AS $$
DECLARE
    heartbeat_timestamp timestamptz = clock_timestamp();
BEGIN
    UPDATE ai.vectorizer_worker_process SET 
          last_heartbeat = heartbeat_timestamp 
        , heartbeat_count = heartbeat_count + 1 
        , error_count = error_count + num_errors_since_last_heartbeat
        , success_count = success_count + num_successes_since_last_heartbeat
        , last_error_message = CASE WHEN error_message IS NOT NULL THEN error_message ELSE last_error_message END 
        , last_error_at = CASE WHEN error_message IS NOT NULL THEN heartbeat_timestamp ELSE last_error_at END 
    WHERE id = worker_id;
END;
$$ LANGUAGE plpgsql security invoker
set search_path to pg_catalog, pg_temp;

CREATE OR REPLACE FUNCTION ai._worker_progress(worker_id uuid, worker_vectorizer_id int, num_successes int, error_message text) RETURNS void AS $$
DECLARE
    progress_timestamp timestamptz = clock_timestamp();
BEGIN
    IF NOT EXISTS (SELECT 1 FROM ai.vectorizer_worker_progress WHERE vectorizer_id = worker_vectorizer_id) THEN
        --make sure a row exists for this vectorizer
        INSERT INTO ai.vectorizer_worker_progress (vectorizer_id) VALUES (worker_vectorizer_id) ON CONFLICT DO NOTHING;
    END IF;

    UPDATE ai.vectorizer_worker_progress SET 
        last_success_at = CASE WHEN error_message IS NULL THEN progress_timestamp ELSE last_success_at END
      , last_success_process_id = CASE WHEN error_message IS NULL THEN worker_id ELSE last_success_process_id END
      , last_error_at = CASE WHEN error_message IS NULL THEN last_error_at ELSE progress_timestamp END
      , last_error_message = CASE WHEN error_message IS NULL THEN last_error_message ELSE error_message END
      , last_error_process_id = CASE WHEN error_message IS NULL THEN last_error_process_id ELSE worker_id END
      , success_count = success_count + num_successes
      , error_count = error_count + CASE WHEN error_message IS NULL THEN 0 ELSE 1 END
    WHERE vectorizer_id = worker_vectorizer_id;
END;
$$ LANGUAGE plpgsql security invoker
set search_path to pg_catalog, pg_temp;