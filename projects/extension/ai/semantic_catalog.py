import json
from typing import Generator, Optional, TypedDict

class GeneratedDescription(TypedDict):
    name: str
    description: str


def render_obj_sample(plpy, relation: str) -> str:
    result = plpy.execute(f"select * from {relation}", 5)

    ret_obj = f"""<data id="{relation}">"""
    for r in result:
        ret_obj += f"""\n  insert into {relation} ({', '.join(r.keys())}) values ({', '.join([str(v) for v in r.values()])});"""
    ret_obj += "\n</data>"

    return ret_obj


def get_parsed_config(plpy, catalog_name: str, config: Optional[dict]) -> dict:
    if config is None:
        result = plpy.execute(f"select x.text_to_sql from ai.semantic_catalog x where x.catalog_name = '{catalog_name}';")
        if len(result) > 0:
            config = result[0]['text_to_sql']

    if config is None:
        raise Exception("No config found")

    return json.loads(config)  # type: dict


def get_obj_description(plpy, relation: str) -> str:
    result = plpy.execute(f"select ai.render_semantic_catalog_obj(0, 'pg_catalog.pg_class'::pg_catalog.regclass::pg_catalog.oid, '{relation}'::pg_catalog.regclass::pg_catalog.oid) as description;")
    return result[0]['description']


def map_tools_to_openai(tools: list) -> list:
    return list(map(lambda x: {"type": "function", "function": {"name": x['name'], "description": x['description'], "parameters": x['input_schema']}}, tools))


def generate_description(
    plpy,
    relation: str,
    catalog_name: str,
    config: Optional[dict],
    save: bool,
    overwrite: bool,
) -> Generator[GeneratedDescription, None, None]:
    """
    Generates a description of a table or view
    """
    parsed_config = get_parsed_config(plpy, catalog_name, config)

    description = "None"

    system_prompt = """
    You are a SQL expert generates natural language descriptions of tables and views in a database.

    The descriptions that you generate should be a concise single sentence.
    """
    message_content = f"""
    Given the following table or view and some sample rows from it, generate a natural language description of it:

    {get_obj_description(plpy, relation)}
    {render_obj_sample(plpy, relation)}
    """
    tools = [
        {
            "name": "generate_description",
            "description": "Record description of table or view in well-formed JSON",
            "input_schema": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Description of the table or view"
                    }
                }
            }
        }
    ]

    provider = parsed_config.get('provider', None)
    if provider == 'anthropic':
        model = parsed_config.get('model', 'claude-3-5-sonnet-latest')
        messages = [{"role": "user", "content": message_content}]

        result = plpy.execute(f"""
            select ai.anthropic_generate(
                '{model}'
                , '{json.dumps(messages).replace("'", "''")}'::jsonb
                , system_prompt => '{system_prompt}'
                , tools => '{json.dumps(tools)}'::jsonb
                , tool_choice => '{{"type": "tool", "name": "generate_description"}}'::jsonb
            )
        """)
        response = json.loads(result[0]['anthropic_generate'])
        description = response['content'][0]['input']['description']
    elif provider == 'ollama':
        pass
    elif provider == 'openai':
        model = parsed_config.get('model', 'gpt-4o')
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": message_content}]
        result = plpy.execute(f"""
            select ai.openai_chat_complete(
                '{model}'
                , '{json.dumps(messages).replace("'", "''")}'::jsonb
                , tools => '{json.dumps(map_tools_to_openai(tools))}'::jsonb
                , tool_choice => '{{"type": "function", "function": {{"name": "generate_description"}}}}'
            )
        """)
        response = json.loads(result[0]['openai_chat_complete'])
        description = json.loads(response['choices'][0]['message']['tool_calls'][0]['function']['arguments'])['description']
    elif provider == 'cohere':
        pass
    else:
        raise Exception(f"provider {provider} not found")

    if save:
        result = plpy.execute(f"select 1 from ai.semantic_catalog_obj x where x.objsubid = 0 and x.classid = 'pg_catalog.pg_class'::pg_catalog.regclass::pg_catalog.oid and x.objid = '{relation}'::pg_catalog.regclass::pg_catalog.oid")
        if len(result) == 0 or overwrite:
            plpy.debug(f"set description for {relation} (existing={len(result) > 0}, overwrite={overwrite})")
            plpy.execute(f"select ai.set_description('{relation}', '{description}'")
    yield relation, description


def generate_column_descriptions(
    plpy,
    relation: str,
    catalog_name: str,
    config: Optional[dict],
    save: bool,
    overwrite: bool,
) -> Generator[tuple[str, str], None, None]:
    parsed_config = get_parsed_config(plpy, catalog_name, config)

    column_names = []
    result = plpy.execute(f"""
    SELECT attname AS col
    FROM   pg_attribute
    WHERE  attrelid = '{relation}'::regclass
    AND    attnum > 0
    AND    NOT attisdropped;
    """)
    for r in result:
        column_names.append(r['col'])
    lines = get_obj_description(plpy, relation).split('\n')
    filtered_lines = [line for line in lines if not any(line.strip().lstrip('/* ').startswith(col) for col in column_names)]
    obj_description = '\n'.join(filtered_lines)

    columns = []
    system_prompt = """
    You are a SQL expert generates natural language descriptions of columns of tables and views in a database.

    The descriptions that you generate should be a concise single sentence.
    You should include case sensitivity in your description if it is relevant.
    """
    message_content = f"""
    Given the following table or view and some sample rows from it, generate a natural language description of all columns:

    {obj_description}
    {render_obj_sample(plpy, relation)}
    """
    messages = [{"role": "user", "content": message_content}]
    tools = [
        {
            "name": "generate_description",
            "description": "Record description of the columns of the table or view in well-formed JSON",
            "input_schema": {
                "type": "object",
                "properties": {
                    "columns": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Name of the column"
                                },
                                "description": {
                                    "type": "string",
                                    "description": "Description of the column"
                                }
                            }
                        }
                    }
                }
            }
        }
    ]
    provider = parsed_config.get('provider', None)
    if provider == 'anthropic':
        model = parsed_config.get('model', 'claude-3-5-sonnet-latest')
        result = plpy.execute(f"""
            SELECT ai.anthropic_generate(
                '{model}'
                , '{json.dumps(messages).replace("'", "''")}'::jsonb
                , system_prompt => '{system_prompt}'
                , tools => '{json.dumps(tools)}'::jsonb
                , tool_choice => '{{"type": "tool", "name": "generate_description"}}'::jsonb
            )
        """)
        columns = json.loads(result[0]['anthropic_generate'])['content'][0]['input']['columns']

    elif provider == 'ollama':
        pass
    elif provider == 'openai':
        model = parsed_config.get('model', 'gpt-4o')
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": message_content}]
        openai_tools = map_tools_to_openai(tools)
        result = plpy.execute(f"""
            select ai.openai_chat_complete(
                '{model}'
                , '{json.dumps(messages).replace("'", "''")}'::jsonb
                , tools => '{json.dumps(openai_tools)}'::jsonb
                , tool_choice => '{{"type": "function", "function": {{"name": "generate_description"}}}}'
            )
        """)
        response = json.loads(result[0]['openai_chat_complete'])
        columns = json.loads(response['choices'][0]['message']['tool_calls'][0]['function']['arguments'])['columns']
    elif provider == 'cohere':
        pass
    else:
        raise Exception(f"provider {provider} not found")

    if save:
        result = plpy.execute(f"select objnames from ai.semantic_catalog_obj x where x.objsubid > 0 and x.classid = 'pg_catalog.pg_class'::pg_catalog.regclass::pg_catalog.oid and x.objid = '{relation}'::pg_catalog.regclass::pg_catalog.oid")
        existing_columns = dict()
        for r in result:
            existing_columns[r['objnames'][-1]] = True

        for column in columns:
            exists = column['name'] in existing_columns
            if not exists or overwrite:
                plpy.debug(f"set description for {column['name']} (existing={exists}, overwrite={overwrite})")
                plpy.execute(f"select ai.set_column_description('{relation}', '{column['name']}', '{column['description']}')")
    for column in columns:
        yield column['name'], column['description']
