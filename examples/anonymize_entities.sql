-- Extract entities example: https://github.com/anthropics/anthropic-cookbook/tree/main/tool_use
\getenv anthropic_api_key ANTHROPIC_API_KEY

SELECT ai.anthropic_generate( 'claude-3-5-sonnet-20240620'
, jsonb_build_array(
    jsonb_build_object(
      'role', 'user',
      'content', 'John works at Google in New York. He met with Sarah, the CEO of Acme Inc., last week in San Francisco.'
    )
  )
, _max_tokens => 4096
, _api_key => $1
, _tools => jsonb_build_array(
    jsonb_build_object(
      'name', 'anonymize_recognized_entities',
      'description', 'Anonymize recognized entities like people names, locations, companies. The output should be the original text with entities replaced by the entities recognized in the input text. Example input: John works at Google in New York. Example output: :PERSON works at :COMPANY in :CITY.',
      'input_schema', jsonb_build_object(
        'type', 'object',
        'anonymized', jsonb_build_object(
            'type', 'text',
            'description', 'The original text anonymized with entities replaced by placeholders with the type of entity recognized.'
         ),
        'required', jsonb_build_array('anonimized_text')
        )
      )
    )
  ) AS result
\bind :anthropic_api_key
\g
