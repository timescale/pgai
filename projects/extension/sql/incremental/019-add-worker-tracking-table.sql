CREATE TABLE ai.vectorizer_worker_process(
        id uuid not null primary key default gen_random_uuid()
    ,   version text not null
    ,   started timestamptz not null default now()
    ,   expected_heartbeat_interval interval not null
    ,   last_heartbeat timestamptz not null default now()
    ,   heartbeat_count int not null default 0
    ,   error_count int not null default 0
    ,   success_count int not null default 0
    ,   last_error_at timestamptz null default null
    ,   last_error_message text null default null
);

create index on ai.vectorizer_worker_process (last_heartbeat);


create table ai.vectorizer_worker_progress(
      vectorizer_id int primary key not null references ai.vectorizer (id) on delete cascade
    , success_count int not null default 0
    , error_count int not null default 0
    , last_success_at timestamptz null default null
    -- don't use foreign key here because of three reasons:
    -- 1. we don't want to enforce that the process exists in the process table (we may want to clean up that table independently)
    -- 2. we don't want have any chance this row will fail to be inserted.
    -- 3. we want the insert of this row to be as fast and lightweight as possible.
    , last_success_process_id uuid null default null
    , last_error_at timestamptz null default null
    , last_error_message text null default null
    --see reasons above for why we don't use foreign key here
    , last_error_process_id uuid null default null
);
