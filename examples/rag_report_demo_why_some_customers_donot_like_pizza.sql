
----------------------------------------------------------------------------------
-- Introduction
----------------------------------------------------------------------------------
-- The demo of AI RAG by generate a why customer don't like pizza report.
-- The input is 3 records of customer comments to pizza food
-- the output is ai result table with 3 columns:send_message, chat_completion,  final_report
-- the final report columns are markdown formatted business analysis report to why customer don't like pizza

-- the process/tools:
	--- vector database: pgai container for run an store the input, output data
    --- ai model service: openai 'gpt-4o-mini','text-embedding-3-small'
    --- the RAG concept of the process


----------------------------------------------------------------------------------
-- Step 1. Preconfig & Check environment
----------------------------------------------------------------------------------
-- clean the history test table
DROP TABLE IF EXISTS  PUBLIC.pizza_reviews  CASCADE;   -- CUSTOMER FEEDBACK STORED HERE
DROP TABLE IF EXISTS PUBLIC.pizza_reviews_embeddings CASCADE;  -- CUSTOMER FEEDBACK EMBEDDED 
DROP TABLE IF EXISTS  PUBLIC.ai_report CASCADE;      -- THE AI GENERATED BUSINESS REPORT

CREATE EXTENSION IF NOT EXISTS ai CASCADE;

-- use openai-4o-mini and text-embedding-3-small models for demo purpose. You can use local ollama based on business case
-- make sure the model connection and availability
-- temporary set the api_key
set ai.openai_api_key = 'replace you api key here or use pgai default api_key environment';
select pg_catalog.current_setting('ai.openai_api_key', true) as api_key;


----------------------------------------------------------------------------------
---- step 2 create customer feedback data table and insert the demo data.
----------------------------------------------------------------------------------

--- the original customer feedback message to food 
CREATE TABLE public.pizza_reviews  (
id bigserial NOT NULL,
product text NOT NULL,
customer_message text NULL,
text_length INTEGER GENERATED ALWAYS AS (LENGTH(customer_message)) stored,
CONSTRAINT pizza_reviews_pkey PRIMARY KEY (id)
);

--- insert data of pizza_reviews 
INSERT INTO public.pizza_reviews  (product,customer_message) VALUES
	 ('pizza','The best pizza I''ve ever eaten. The sauce was so tangy!'),
	 ('pizza','The pizza was disgusting. I think the pepperoni was made from rats.'),
	 ('pizza','I ordered a hot-dog and was given a pizza, but I ate it anyway.'),
	 ('pizza','I hate pineapple on pizza. It is a disgrace. Somehow, it worked well on this izza though.'),
	 ('pizza','I ate 11 slices and threw up. The pizza was tasty in both directions.');

-- the data of embedding result
CREATE TABLE public.pizza_reviews_embeddings (
id bigserial NOT NULL,
text_id text NOT NULL, 
text_content text NOT NULL, -- it is same as pizza_reviews 
model_name text NOT NULL,
ntoken int4 NULL,
nlength int4 NULL,
embedding public.vector(1536) NOT NULL,
CONSTRAINT pizza_reviews_embeddings_pkey PRIMARY KEY (id)
);


-- the ai report for store final customer satisfaction report build by ai.
CREATE TABLE public.ai_report (
	send_message text NULL,
	chat_completion jsonb NULL,
	final_report text NULL,
	create_time timestamptz NULL
);

----------------------------------------------------------------------------------
-- step 3. Convert the original customer message to food into vector
----------------------------------------------------------------------------------
-- get embedding result and insert into the embedding table 
with tmp as (
select
	tt.id, tt.customer_message,
	'text-embedding-3-small'::text as model_name,
	openai_embed('text-embedding-3-small',customer_message) as embedding
from
	pizza_reviews  as tt
)
insert into pizza_reviews_embeddings 
		(text_id, text_content, model_name, embedding )
	select 
		id, customer_message, model_name, embedding
	from 
		tmp;

--- create index for query speed optimization. It is optional for small data demo 
CREATE INDEX ON pizza_reviews_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists='5');
	

----------------------------------------------------------------------------------
-- step 4. Using AI chat_completion and Database to fast answer busines Question
----------------------------------------------------------------------------------

-- After make the history data into vector table, the new business question could be answered via RAG mod
-- RAG mean convert question to vector and compare it to history data which vectored, find the most similar record.
--- and send to chat_completion for generate business insight report.
--- show the top3  relevant customer message to business question.
with
business_question as (
	select question 
	from 
		(values 
			('why customer do not like our pizza?')
			)as t(question)	
)
, embedding_question as (
	select 
		question, openai_embed('text-embedding-3-small',question) as embedding 
	from
		business_question
)
select
	eqt.question, 
	emt.text_content , 
	emt.embedding <-> eqt.embedding as similarity
from pizza_reviews_embeddings emt  cross join embedding_question eqt
order by emt.embedding <-> eqt.embedding
limit 3;
-- note 
-- in demo case, limit 3 is used as criteria of select history data, 
-- in real business,  the criteria value should be choice with business needs.


----------------------------------------------------------------------------------
-- step 5. Final step, let's generate a nice business report based on above finding by chat_completion
----------------------------------------------------------------------------------
-- create a build_pizza_report function to put a ai instruction in it, and call it by one sql command.
CREATE OR REPLACE FUNCTION build_pizza_report(_question text, _n_criteria smallint)
RETURNS SETOF ai_report AS
$$
BEGIN
RETURN QUERY
    
with
embedding_question as (
	select 
		_question as question, openai_embed('text-embedding-3-small',_question) as embedding
	), 
reasons as (
	select
		eqt.question, 
		emt.text_content , 
		emt.embedding <-> eqt.embedding as similarity
	from pizza_reviews_embeddings emt  cross join embedding_question eqt
	order by 
		emt.embedding <-> eqt.embedding
		limit _n_criteria
	)
,agg_resons as (
 	select 
 		question,  jsonb_pretty(jsonb_agg(text_content)) as reasons
 	from reasons
 	group by question
	)
,report_needs as (
	select 
	chr(10)||'// 1. requirements:
	// 1.1 generate a business report to answer user question with provided data.
	// 1.2 The report should be markdown format and less than 300 words' || chr(10) as report_needs,
	chr(10)||'// 2. data' || chr(10)as data_needs,
	chr(10)||'// 3. user question'|| chr(10)as user_question
 	)
,ai_report as (
		select 
			report_needs || data_needs ||  reasons  ||user_question || question as send_message,
			openai_chat_complete(
			'gpt-4o-mini',
			jsonb_build_array(
				jsonb_build_object(
					'role', 'user', 'content', 
					report_needs || data_needs ||  reasons  ||user_question || question)
			)) as chat_completion
		from 
			agg_resons cross join report_needs

)
select 
	send_message, chat_completion,
	replace(chat_completion['choices'][0]['message']['content']::text,'\n',chr(10)) as final_report,
	now() as create_time
--into ai_report
from ai_report;

    
END;
$$
LANGUAGE plpgsql;

---- call the build_pizza_report now

insert into ai_report (send_message, chat_completion,final_report,create_time) 
select  
  send_message, chat_completion,final_report,create_time
from 
	build_pizza_report('why customer dont like our pizza'::text,3::int2);
select * from ai_report ;

