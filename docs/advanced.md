# Advanced Examples

This page gives you more in-depth AI examples using pgai. In these examples, you 
will use pgai to embed, moderate, and summarize git commit history.

- [Install the advanced examples]() - add git commit history sample data to your database
- [Embedding]() - generate an [embedding](https://platform.openai.com/docs/guides/embeddings) for each git commit
- [Moderation]() - check the commit history and flag harmful speech in a new table
- [Summerization]() - summarize a month of git commits in a Markdown release note 

## Install the advanced examples

To add the advanced examples to your developer environment:

1. Connect to your database using the `psql` command line tool and pass your 
   OPENAI API key as a psql variable from your environment. Run this from the
   directory where the csv file resides.

   ```bash
   psql -d "postgres://<username>:<password>@<host>:<port>/<database-name>" -v OPENAI_API_KEY=$OPENAI_API_KEY
   ```

3. Ensure pgai is enabled on your database and add the [git commit_history data](./commit_history.csv) to a new table in your database.

   ```sql
   create extension if not exists ai cascade;
   
   -- a table with git commit history
   create table commit_history
   ( id int not null primary key
   , author text
   , "date" timestamptz
   , "commit" text
   , summary text
   , detail text
   );
   
   -- use psql's copy metacommand to load the csv into the table
   -- if the csv file is not in the same directory from which psql was launched,
   -- you will need to modify the path here
   \copy commit_history from 'commit_history.csv' with (format csv)
   ```

## Embedding

The following example uses the pgai extension to generate an embedding for each
git commit. These are inserted into a new table.

```sql
-- we want to embed each row of commit history and put the embedding in this table
create table commit_history_embed
( id int not null primary key
, embedding vector(1536) -- the vector type comes from the pgvector extension
);

-- select from the first table, embed the content, and insert in the second table
insert into commit_history_embed (id, embedding)
select
  id
, openai_embed
  ( $1
  , 'text-embedding-3-small'
    -- create a single text string representation of the commit
  , format('author: %s date: %s commit: %s summary: %s detail: %s', author, "date", "commit", summary, detail)
  ) as embedding
from commit_history
\bind :OPENAI_API_KEY
\g
```

## Moderation

Use the pgai extension to moderate the git commit details. Any
commits that are flagged are inserted into a new table. An array of the 
categories of harmful speech that were flagged is provided for each row. We
use both [jsonb operators](https://www.postgresql.org/docs/current/functions-json.html#FUNCTIONS-JSON-PROCESSING)
and a [jsonpath query](https://www.postgresql.org/docs/current/functions-json.html#FUNCTIONS-SQLJSON-PATH) 
to process [the response](https://platform.openai.com/docs/api-reference/moderations/object)
from OpenAI to acheive this.

```sql
create table commit_history_moderated 
( id int not null primary key
, detail text -- the content that was moderated
, flagged_categories jsonb -- an array of json strings
);

insert into commit_history_moderated (id, detail, flagged_categories)
select
  x.id
, x.detail
  -- pull out the list of only the categories that were flagged
, jsonb_path_query_array(x.moderation, '$.results[0].categories.keyvalue() ? (@.value == true).key')
from
(
    select
      id
    , detail
      -- call the openai api using the pgai extension. the result is jsonb
    , openai_moderate($1, 'text-moderation-stable', detail) as moderation
    from commit_history
) x
where (x.moderation->'results'->0->>'flagged')::bool -- only the ones that were flagged
\bind :OPENAI_API_KEY
\g
```

## Summerization

Use the pgai extension to summarize content. In a single query, ask for a summarization 
of a month's worth of git commits in the form of release notes in Markdown format. You 
provide one message for the system and another one for the user. 

The git commits for the month are appended in text format to the user message. The query 
uses jsonb operators to pull out the content of the [response](https://platform.openai.com/docs/api-reference/chat/object) only.

```sql
-- summarize and categorize git commits to produce a release notes document
select openai_chat_complete
( $1
, 'gpt-4o'
, jsonb_build_array
  ( jsonb_build_object
    ( 'role', 'system'
    , 'content', 'You are a software release engineer who summarizes git commits to produce release notes.'
    )
  , jsonb_build_object
    ( 'role', 'user'
    , 'content'
    , -- build up a list of the commit details to append to the prompt
      concat
      ( E'Summarize the following list of commits from the timescaledb git repo from August 2023 in a release notes document in markdown format.\n\n'
      , string_agg(x.commit_desc, E'\n\n')
      )
    )
  )
)->'choices'->0->'message'->>'content'
from
(
    -- convert each to a text format
    select format
    ( E'%s %s\n\tcommit: %s\n\tauthor: %s\n\tdate: %s\n\tdetail: %s'
    , row_number() over (order by "date")
    , summary
    , "commit"
    , author
    , "date"
    , detail
    ) as commit_desc
    from commit_history
    -- just look at commits from August 2023
    where date_trunc('month', "date") = '2023-08-01 00:00:00-05'::timestamptz
    order by "date"
) x
\bind :OPENAI_API_KEY
\g
```
