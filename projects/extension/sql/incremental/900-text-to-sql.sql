--FEATURE-FLAG: text_to_sql

create table ai.description
( objtype pg_catalog.text not null      -- required for dump/restore to function
, objnames pg_catalog.text[] not null   -- required for dump/restore to function
, objargs pg_catalog.text[] not null    -- required for dump/restore to function
, classid pg_catalog.oid not null       -- required for event triggers to function
, objid pg_catalog.oid not null         -- required for event triggers to function
, objsubid pg_catalog.int4 not null     -- required for event triggers to function
, description pg_catalog.text not null  -- the description
, primary key (objtype, objnames, objargs)
);
create index on ai.description (classid, objid, objsubid);

/*
pg_identify_object_as_address translates
classid + objid + objsubid -> objtype + objnames + objargs

pg_get_object_address translates
objtype + objnames + objargs -> classid + objid + objsubid

and we can support descriptions for any db obj type that supports COMMENT
*/
