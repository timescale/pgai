
-- TODO: remove feature flag
select set_config('ai.enable_feature_flag_text_to_sql', 'true', false);
create extension if not exists ai cascade;

create schema bishop;

create table public.xenomorph
( id int not null primary key
, foo text not null
, bar timestamptz not null default now()
);
select ai.set_description ('public.xenomorph', 'description for xenomorph');
select ai.set_column_description('public.xenomorph', 'id', 'description for xenomorph.id');
select ai.set_column_description('public.xenomorph', 'foo', 'description for xenomorph.foo');
select ai.set_column_description('public.xenomorph', 'bar', 'description for xenomorph.bar');

create table bishop.ripley
( id int not null primary key
, foo text not null
, bar timestamptz not null default now()
);
select ai.set_description('bishop.ripley', 'description for bishop.ripley');
select ai.set_column_description('bishop.ripley', 'id', 'description for bishop.ripley.id');
select ai.set_column_description('bishop.ripley', 'foo', 'description for bishop.ripley.foo');
select ai.set_column_description('bishop.ripley', 'bar', 'description for bishop.ripley.bar');

create view public.hicks as
select * from bishop.ripley;
select ai.set_description('public.hicks', 'description for hicks');
select ai.set_column_description('public.hicks', 'id',  'description for hicks.id');
select ai.set_column_description('public.hicks', 'foo', 'description for hicks.foo');
select ai.set_column_description('public.hicks', 'bar', 'description for hicks.bar');

create function public.hudson(x int) returns int
as $func$
    select 42
$func$ language sql
;
select ai.set_function_description('public.hudson'::regproc, 'description for hudson(int)');

create function public.hudson(x int, y int) returns int
as $func$
    select 42
$func$ language sql
;
select ai.set_function_description('public.hudson(int, int)', 'description for hudson(int, int)');

create table bishop.burke
( id int not null primary key
, foo text
, bar text
, baz bool
);
select ai.set_description('bishop.burke', 'description for bishop.burke');
select ai.set_column_description('bishop.burke', 'id', 'description for bishop.burke.id');
select ai.set_column_description('bishop.burke', 'foo', 'description for bishop.burke.foo');
select ai.set_column_description('bishop.burke', 'bar', 'description for bishop.burke.bar');

create function bishop.gorman(z bool) returns int
as $func$
    select 42
$func$ language sql
;
select ai.set_function_description('bishop.gorman(bool)', 'description for bishop.gorman(bool)');


