import json
from collections.abc import Generator
from typing import TypedDict


class GeneratedDescription(TypedDict):
    name: str
    description: str


def render_sample(plpy, relation: str, total: int = 5) -> str:
    ident = ".".join([plpy.quote_ident(part) for part in relation.split(".")])
    result = plpy.execute(f"select * from {ident}", total)

    ret_obj = f"""<data id="{relation}">"""
    for r in result:
        values = []
        for v in r.values():
            if isinstance(v, str) or v is None:
                values.append(plpy.quote_nullable(v))
            elif isinstance(v, bool):
                values.append("true" if v else "false")
            else:
                values.append(str(v))
        ret_obj += f"""\n  insert into {ident} ({', '.join(plpy.quote_ident(key) for key in r.keys())}) values ({', '.join(values)});"""
    ret_obj += "\n</data>"

    return ret_obj


def get_parsed_config(plpy, catalog_name: str, config: dict | None) -> dict:
    if config is None:
        plan = plpy.prepare(
            "select x.text_to_sql from ai.semantic_catalog x where x.catalog_name = $1",
            ["text"],
        )
        result = plpy.execute(
            plan,
            [catalog_name],
            1,
        )
        if len(result) > 0:
            config = result[0]["text_to_sql"]

    if config is None:
        raise Exception("No config found")

    return json.loads(config)  # type: dict


def get_obj_description(
    plpy, relation: str | None = None, fn: str | None = None
) -> str:
    if relation:
        result = plpy.execute(
            f"select ai.render_semantic_catalog_obj(0, 'pg_catalog.pg_class'::pg_catalog.regclass::pg_catalog.oid, {plpy.quote_literal(relation)}::pg_catalog.regclass::pg_catalog.oid) as description"
        )
    else:
        result = plpy.execute(
            f"select ai.render_semantic_catalog_obj(0, 'pg_catalog.pg_proc'::pg_catalog.regclass::pg_catalog.oid, {plpy.quote_literal(fn)}::regprocedure::pg_catalog.oid) as description"
        )
    return result[0]["description"]


def map_tools_to_openai(tools: list) -> list:
    return list(
        map(
            lambda x: {
                "type": "function",
                "function": {
                    "name": x["name"],
                    "description": x["description"],
                    "parameters": x["input_schema"],
                },
            },
            tools,
        )
    )


def generate_description(
    plpy,
    relation: str,
    catalog_name: str,
    config: dict | None,
    save: bool,
    overwrite: bool,
) -> Generator[GeneratedDescription, None, None]:
    """
    Generates a description of a table or view
    """
    result = plpy.execute(
        f"select 1 from ai.semantic_catalog_obj x where x.objsubid = 0 and x.classid = 'pg_catalog.pg_class'::pg_catalog.regclass::pg_catalog.oid and x.objid = {plpy.quote_literal(relation)}::pg_catalog.regclass::pg_catalog.oid limit 1"
    )
    if len(result) == 1 and not overwrite:
        yield from []
        return

    parsed_config = get_parsed_config(plpy, catalog_name, config)

    system_prompt = """
    You are a SQL expert generates natural language descriptions of tables and views in a database.

    The descriptions that you generate should be a concise single sentence.
    """
    message_content = f"""
    Given the following table or view and some sample rows from it, generate a natural language description of it:

    {get_obj_description(plpy, relation)}
    {render_sample(plpy, relation)}
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
                        "description": "Description of the table or view",
                    }
                },
            },
        }
    ]

    provider = parsed_config.get("provider", None)
    if provider == "anthropic":
        model = parsed_config.get("model", "claude-3-5-sonnet-latest")
        messages = [{"role": "user", "content": message_content}]

        plan = plpy.prepare(
            """
                select ai.anthropic_generate(
                    $1
                    , $2
                    , system_prompt => $3
                    , tools => $4
                    , tool_choice => '{"type": "tool", "name": "generate_description"}'::jsonb
                )
            """,
            ["text", "jsonb", "text", "jsonb"],
        )
        result = plpy.execute(
            plan, [model, json.dumps(messages), system_prompt, json.dumps(tools)]
        )
        response = json.loads(result[0]["anthropic_generate"])
        description = response["content"][0]["input"]["description"]
    elif provider == "ollama":
        raise NotImplementedError("ollama provider not implemented")
    elif provider == "openai":
        model = parsed_config.get("model", "gpt-4o")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message_content},
        ]
        plan = plpy.prepare(
            """
                select ai.openai_chat_complete(
                    $1
                    , $2
                    , tools => $3
                    , tool_choice => '{"type": "function", "function": {"name": "generate_description"}}'::jsonb
                )
            """,
            ["text", "jsonb", "jsonb"],
        )
        result = plpy.execute(
            plan, [model, json.dumps(messages), json.dumps(map_tools_to_openai(tools))]
        )
        response = json.loads(result[0]["openai_chat_complete"])
        description = json.loads(
            response["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
        )["description"]
    elif provider == "cohere":
        raise NotImplementedError("cohere provider not implemented")
    else:
        raise Exception(f"provider {provider} not found")

    sql = f"select ai.set_description({plpy.quote_literal(relation)}, {plpy.quote_literal(description)})"
    if save:
        plpy.debug(
            f"set description for {relation} (existing={len(result) > 0}, overwrite={overwrite})"
        )
        plpy.execute(sql)

    yield relation, description, sql


def generate_column_descriptions(
    plpy,
    relation: str,
    catalog_name: str,
    config: dict | None,
    save: bool,
    overwrite: bool,
) -> Generator[list[GeneratedDescription], None, None]:
    parsed_config = get_parsed_config(plpy, catalog_name, config)

    column_names = []
    result = plpy.execute(f"""
    SELECT attname AS col
    FROM   pg_attribute
    WHERE  attrelid = {plpy.quote_literal(relation)}::regclass
    AND    attnum > 0
    AND    NOT attisdropped;
    """)
    for r in result:
        column_names.append(r["col"])
    lines = get_obj_description(plpy, relation).split("\n")
    filtered_lines = [
        line
        for line in lines
        if not any(line.strip().lstrip("/* ").startswith(col) for col in column_names)
    ]
    obj_description = "\n".join(filtered_lines)

    columns = []
    system_prompt = """
    You are a SQL expert generates natural language descriptions of columns of tables and views in a database.

    The descriptions that you generate should be a concise single sentence.
    You should include case sensitivity in your description if it is relevant.
    """
    message_content = f"""
    Given the following table or view and some sample rows from it, generate a natural language description of all columns:

    {obj_description}
    {render_sample(plpy, relation)}
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
                                    "description": "Name of the column",
                                },
                                "description": {
                                    "type": "string",
                                    "description": "Description of the column",
                                },
                            },
                        },
                    }
                },
            },
        }
    ]
    provider = parsed_config.get("provider", None)
    if provider == "anthropic":
        model = parsed_config.get("model", "claude-3-5-sonnet-latest")
        plan = plpy.prepare(
            """
                SELECT ai.anthropic_generate(
                    $1
                    , $2
                    , system_prompt => $3
                    , tools => $4
                    , tool_choice => '{"type": "tool", "name": "generate_description"}'::jsonb
                )
            """,
            ["text", "jsonb", "text", "jsonb"],
        )
        result = plpy.execute(
            plan, [model, json.dumps(messages), system_prompt, json.dumps(tools)]
        )
        columns = json.loads(result[0]["anthropic_generate"])["content"][0]["input"][
            "columns"
        ]

    elif provider == "ollama":
        raise NotImplementedError("ollama provider not implemented")
    elif provider == "openai":
        model = parsed_config.get("model", "gpt-4o")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message_content},
        ]
        plan = plpy.prepare(
            """
                select ai.openai_chat_complete(
                    $1
                    , $2
                    , tools => $3
                    , tool_choice => '{"type": "function", "function": {"name": "generate_description"}}'::jsonb
                )
            """,
            ["text", "jsonb", "jsonb"],
        )
        result = plpy.execute(
            plan, [model, json.dumps(messages), json.dumps(map_tools_to_openai(tools))]
        )
        response = json.loads(result[0]["openai_chat_complete"])
        columns = json.loads(
            response["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
        )["columns"]
    elif provider == "cohere":
        raise NotImplementedError("cohere provider not implemented")
    else:
        raise Exception(f"provider {provider} not found")

    result = plpy.execute(
        f"select objnames from ai.semantic_catalog_obj x where x.objsubid > 0 and x.classid = 'pg_catalog.pg_class'::pg_catalog.regclass::pg_catalog.oid and x.objid = {plpy.quote_literal(relation)}::pg_catalog.regclass::pg_catalog.oid"
    )
    existing_columns = dict()
    for r in result:
        existing_columns[r["objnames"][-1]] = True

    yielded = False
    for column in columns:
        exists = column["name"] in existing_columns
        if not exists or overwrite:
            plpy.debug(
                f"set description for {column['name']} (existing={exists}, overwrite={overwrite})"
            )
            sql = f"select ai.set_column_description({plpy.quote_literal(relation)}, {plpy.quote_literal(column['name'])}, {plpy.quote_literal(column['description'])})"
            if save:
                plpy.execute(sql)
            yield column["name"], column["description"], sql
            yielded = True
    if not yielded:
        yield from []


def generate_function_description(
    plpy,
    fn: str,
    catalog_name: str,
    config: dict | None,
    save: bool,
    overwrite: bool,
) -> Generator[GeneratedDescription, None, None]:
    result = plpy.execute(
        f"select 1 from ai.semantic_catalog_obj x where x.classid = 'pg_catalog.pg_proc'::pg_catalog.regclass::pg_catalog.oid and x.objid = {plpy.quote_literal(fn)}::regprocedure::pg_catalog.oid"
    )
    if len(result) == 1 and not overwrite:
        yield from []
        return

    parsed_config = get_parsed_config(plpy, catalog_name, config)
    description = "None"
    system_prompt = """
    You are a SQL expert generates natural language descriptions of functions in a database.

    The descriptions that you generate should be a concise single sentence.
    """

    message_content = f"""
    Given the following function, generate a natural language description of it:

    {get_obj_description(plpy, fn=fn)}
    """

    tools = [
        {
            "name": "generate_description",
            "description": "Record description of function in well-formed JSON",
            "input_schema": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Description of the function",
                    }
                },
            },
        }
    ]

    provider = parsed_config.get("provider", None)
    if provider == "anthropic":
        model = parsed_config.get("model", "claude-3-5-sonnet-latest")
        messages = [{"role": "user", "content": message_content}]

        plan = plpy.prepare(
            """
                select ai.anthropic_generate(
                    $1
                    , $2
                    , system_prompt => $3
                    , tools => $4
                    , tool_choice => '{"type": "tool", "name": "generate_description"}'::jsonb
                )
            """,
            ["text", "jsonb", "text", "jsonb"],
        )
        result = plpy.execute(
            plan, [model, json.dumps(messages), system_prompt, json.dumps(tools)]
        )
        response = json.loads(result[0]["anthropic_generate"])
        description = response["content"][0]["input"]["description"]
    elif provider == "ollama":
        raise NotImplementedError("ollama provider not implemented")
    elif provider == "openai":
        model = parsed_config.get("model", "gpt-4o")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message_content},
        ]
        plan = plpy.prepare(
            """
                select ai.openai_chat_complete(
                    $1
                    , $2
                    , tools => $3
                    , tool_choice => '{"type": "function", "function": {"name": "generate_description"}}'::jsonb
                )
            """,
            ["text", "jsonb", "jsonb"],
        )
        result = plpy.execute(
            plan, [model, json.dumps(messages), json.dumps(map_tools_to_openai(tools))]
        )
        response = json.loads(result[0]["openai_chat_complete"])
        description = json.loads(
            response["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
        )["description"]
    elif provider == "cohere":
        raise NotImplementedError("cohere provider not implemented")
    else:
        raise Exception(f"provider {provider} not found")

    plpy.debug(
        f"set description for {fn} (existing={len(result) > 0}, overwrite={overwrite})"
    )
    sql = f"select ai.set_function_description({plpy.quote_literal(fn)}::regprocedure, {plpy.quote_literal(description)})"
    if save:
        plpy.execute(sql)

    yield fn, description, sql
