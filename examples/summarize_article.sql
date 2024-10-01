CREATE OR REPLACE FUNCTION public.summarize_article(article_text text)
RETURNS TABLE(
    author text,
    topics text[],
    summary text,
    coherence integer,
    persuasion numeric
)
AS $$
DECLARE
    api_response jsonb;
    summary_json jsonb;
BEGIN
    -- Call the Anthropic API using the ai.anthropic_generate function with print_summary tool
    SELECT ai.anthropic_generate(
        'claude-3-5-sonnet-20240620',
        jsonb_build_array(
            jsonb_build_object(
                'role', 'user',
                'content', format('Please summarize the following article using the print_summary tool: %s', article_text)
            )
        ),
        _max_tokens => 4096,
        _tools => jsonb_build_array(
            jsonb_build_object(
                'name', 'print_summary',
                'description', 'Prints a summary of the article.',
                'input_schema', jsonb_build_object(
                    'type', 'object',
                    'properties', jsonb_build_object(
                        'author', jsonb_build_object('type', 'string', 'description', 'Name of the article author'),
                        'topics', jsonb_build_object(
                            'type', 'array',
                            'items', jsonb_build_object('type', 'string'),
                            'description', 'Array of topics, e.g. ["tech", "politics"]. Should be as specific as possible, and can overlap.'
                        ),
                        'summary', jsonb_build_object('type', 'string', 'description', 'Summary of the article. One or two paragraphs max.'),
                        'coherence', jsonb_build_object('type', 'integer', 'description', 'Coherence of the article''s key points, 0-100 (inclusive)'),
                        'persuasion', jsonb_build_object('type', 'number', 'description', 'Article''s persuasion score, 0.0-1.0 (inclusive)')
                    ),
                    'required', jsonb_build_array('author', 'topics', 'summary', 'coherence', 'persuasion')
                )
            )
        )
    ) INTO api_response;

    -- Extract the summary from the tool use response
    summary_json := jsonb_path_query(api_response, '$.content[*] ? (@.type == "tool_calls").tool_calls[*].function.arguments')::jsonb;

    -- Return the extracted summary information
    RETURN QUERY
    SELECT
        summary_json->>'author',
        array(SELECT jsonb_array_elements_text(summary_json->'topics')),
        summary_json->>'summary',
        (summary_json->>'coherence')::integer,
        (summary_json->>'persuasion')::numeric;

EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'An error occurred: %', SQLERRM;
        RAISE NOTICE 'API Response: %', api_response;
        RETURN;
END;
$$ LANGUAGE plpgsql;

-- Test the function
-- Content From URL: https://docs.timescale.com/use-timescale/latest/compression
select * from summarize_article($$
  #  Compression

  Time-series data can be compressed to reduce the amount of storage required, and increase the speed of some queries. This is a cornerstone feature of Timescale. When new data is added to your database, it is in the form of uncompressed rows. Timescale uses a built-in job scheduler to convert this data to the form of compressed columns. This occurs across chunks of Timescale hypertables.

   Timescale charges are based on how much storage you use. You don't pay for a fixed storage size, and you don't need to worry about scaling disk size as your data grows; We handle it all for you. To reduce your data costs further, use compression, a data retention policy, and tiered storage.

$$);
-- -[ RECORD 1 ]----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
-- author     | Timescale Documentation
-- topics     | {"database management","data compression","time-series data","data storage optimization"}
-- summary    | The article discusses Timescale's compression feature for time-series data. It explains that compression is a key feature of Timescale, designed to reduce storage requirements and improve query performance. The process involves converting newly added uncompressed row data into compressed columns using a built-in job scheduler. This compression occurs across chunks of Timescale hypertables. The article also mentions that Timescale's pricing model is based on actual storage used, with automatic scaling. To further reduce data costs, users are advised to employ compression, implement data retention policies, and utilize tiered storage.
-- coherence  | 95
-- persuasion | 0.8
