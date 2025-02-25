CREATE TABLE ai.vectorizer_worker_connection(
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

create index on ai.vectorizer_worker_connection (last_heartbeat);


create table ai.vectorizer_worker_progress(
      vectorizer_id int primary key not null references ai.vectorizer (id) on delete cascade
    , success_count int not null default 0
    , error_count int not null default 0
    , last_success_at timestamptz null default null
    , last_success_connection_id uuid null default null
    , last_error_at timestamptz null default null
    , last_error_message text null default null
    , last_error_connection_id uuid null default null
);
