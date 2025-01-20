--FEATURE-FLAG: text_to_sql

-------------------------------------------------------------------------------
-- create_semantic_catalog
create or replace function ai.create_semantic_catalog
( embedding pg_catalog.jsonb default null
, indexing pg_catalog.jsonb default ai.indexing_default()
, scheduling pg_catalog.jsonb default ai.scheduling_default()
, processing pg_catalog.jsonb default ai.processing_default()
, grant_to pg_catalog.name[] default ai.grant_to()
-- TODO: need to specify text search config https://www.postgresql.org/docs/current/textsearch-configuration.html
, text_to_sql pg_catalog.jsonb default null
, catalog_name pg_catalog.name default 'default'
) returns pg_catalog.int4
as $func$
declare
    _catalog_name pg_catalog.name = catalog_name;
    _text_to_sql pg_catalog.jsonb = text_to_sql;
    _catalog_id pg_catalog.int4;
    _obj_vec_id pg_catalog.int4;
    _sql_vec_id pg_catalog.int4;
begin
    grant_to = pg_catalog.array_cat
    ( grant_to
    , array
      [ pg_catalog."session_user"()
      , 'pg_database_owner'::name
      ]
    );

    _catalog_id = pg_catalog.nextval('ai.semantic_catalog_id_seq'::pg_catalog.regclass);

    select ai.create_vectorizer
    ( 'ai.semantic_catalog_obj'::pg_catalog.regclass
    , destination=>pg_catalog.format('semantic_catalog_obj_%s', _catalog_id)
    , embedding=>embedding
    , indexing=>indexing
    , scheduling=>scheduling
    , processing=>processing
    , grant_to=>grant_to
    , formatting=>ai.formatting_python_template() -- TODO: this ain't gonna work
    , chunking=>ai.chunking_recursive_character_text_splitter('description') -- TODO
    ) into strict _obj_vec_id
    ;

    -- TODO: create text search index on vectorizer target table

    select ai.create_vectorizer
    ( 'ai.semantic_catalog_sql'::pg_catalog.regclass
    , destination=>pg_catalog.format('semantic_catalog_sql_%s', _catalog_id)
    , embedding=>embedding
    , indexing=>indexing
    , scheduling=>scheduling
    , processing=>processing
    , grant_to=>grant_to
    , formatting=>ai.formatting_python_template() -- TODO: this ain't gonna work
    , chunking=>ai.chunking_recursive_character_text_splitter('description') -- TODO
    ) into strict _sql_vec_id
    ;

    -- TODO: create text search index on vectorizer target table

    insert into ai.semantic_catalog
    ( id
    , catalog_name
    , obj_vectorizer_id
    , sql_vectorizer_id
    , text_to_sql
    )
    values
    ( _catalog_id
    , _catalog_name
    , _obj_vec_id
    , _sql_vec_id
    , _text_to_sql
    )
    returning id
    into strict _catalog_id
    ;

    return _catalog_id;
end;
$func$ language plpgsql volatile security definer -- definer on purpose!
set search_path to pg_catalog, pg_temp
;
