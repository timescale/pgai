
drop schema if exists bob;
create schema bob;

create table bob.blog
( id int not null generated always as identity
, title text not null
, published timestamptz not null
, content text not null
, primary key (title, published)
);

select ai.vectorize
( 'bob.blog'::regclass
, array['content']
, 768
);

insert into bob.blog (title, published, content)
values ('hot to cook a hot dog', '2024-07-24'::timestamptz, 'put it in the microwave for 1 minute')
;
