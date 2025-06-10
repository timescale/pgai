-- This is required to match with 0.11.0 and later versions. the 030-add_vectorizer_errors_view.sql got fixed by then.
-- We recreate the view to ensure default privileges are set correctly.
-- We cannot use the revoke command on the view, because the output of \z ai.* will show `(none)` for the view, instead of empty privileges.
do $$
declare
    view_def text;
begin
    -- 1. Get the current view definition
    select pg_get_viewdef('ai.vectorizer_errors', true)
    into view_def;

    -- 2. Drop the view
    execute 'drop view ai.vectorizer_errors';

    -- 3. Recreate the view with original definition
    execute format('create view ai.vectorizer_errors as %s', view_def);
end;
$$;