
-- TODO: remove feature flag
select set_config('ai.enable_feature_flag_text_to_sql', 'true', false);
create extension if not exists ai cascade;

create schema billy;

create table public.predator
( id int not null primary key
, foo text not null
, bar timestamptz not null default now()
);
select ai.set_description ('public.predator', 'description for predator');
select ai.set_column_description('public.predator', 'id', 'description for predator.id');
select ai.set_column_description('public.predator', 'foo', 'description for predator.foo');
select ai.set_column_description('public.predator', 'bar', 'description for predator.bar');

create table billy.dillon
( id int not null primary key
, foo text not null
, bar timestamptz not null default now()
);
select ai.set_description('billy.dillon', 'description for billy.dillon');
select ai.set_column_description('billy.dillon', 'id', 'description for billy.dillon.id');
select ai.set_column_description('billy.dillon', 'foo', 'description for billy.dillon.foo');
select ai.set_column_description('billy.dillon', 'bar', 'description for billy.dillon.bar');

create view public.hawkins as
select * from billy.dillon;
select ai.set_description('public.hawkins', 'description for hawkins');
select ai.set_column_description('public.hawkins', 'id',  'description for hawkins.id');
select ai.set_column_description('public.hawkins', 'foo', 'description for hawkins.foo');
select ai.set_column_description('public.hawkins', 'bar', 'description for hawkins.bar');

create function public.dutch(x int) returns int
as $func$
    select 42
$func$ language sql
;
select ai.set_function_description('public.dutch'::regproc, 'description for dutch(int)');

create function public.dutch(x int, y int) returns int
as $func$
    select 42
$func$ language sql
;
select ai.set_function_description('public.dutch(int, int)', 'description for dutch(int, int)');

create table billy.poncho
( id int not null primary key 
, foo text
, bar text
, baz bool
);
select ai.set_description('billy.poncho', 'description for billy.poncho');
select ai.set_column_description('billy.poncho', 'id', 'description for billy.poncho.id');
select ai.set_column_description('billy.poncho', 'foo', 'description for billy.poncho.foo');
select ai.set_column_description('billy.poncho', 'bar', 'description for billy.poncho.bar');

create function billy.mac(z bool) returns int
as $func$
    select 42
$func$ language sql
;
select ai.set_function_description('billy.mac(bool)', 'description for billy.mac(bool)');

select ai.add_sql_example
( $sql$
select id, concat(foo, bar, baz)
from billy.poncho
where id % 2 = 0
$sql$
, $description$
This query concatenates foo, bar, and baz for even ids of billy.poncho.
$description$
);

