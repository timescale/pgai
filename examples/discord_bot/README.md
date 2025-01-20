# Discord Bot

A minimal discord bot that answers questions based on pgais documentation via RAG.
Built with python, py-cord, sqlalchemy and pgai.

## Running the Example

You will need a .env file with the following variables:

```shell
DATABASE_ULR=postgresql+asyncpg://postgres:postgres@localhost/postgres
OPENAI_API_KEY=xxx
DISCORD_BOT_TOKEN=xxx
DISCORD_CHANNEL_ID=123
```

- To get the openai api key you can create one [here](https://platform.openai.com/api-keys).
- To create the discord bot token follow the guide by py-cord [here](https://docs.pycord.dev/en/stable/discord.html#discord-intro).
- The channel id can be found by right clicking on the channel in discord and selecting "Copy ID". You will need to enable developer mode in discord settings to see this option.

You will need to then run the vectorizer and database with:
```
docker compose up -d
```
You'll also need to install the python requirements with:
```shell
uv sync
```

To run the migrations to create_necessary tables run:
```shell
uv run alembic upgrade head
```

To populate the database with our docs run the insert_docs.py script with:
```shell
uv run python insert_docs.py
```

Afterwards you can run the bot with:

```shell
uv run python main.py
```

The bot will answer questions by responding threads in the specified channel.

## Build the docker container
To build the docker container run:
```shell
docker build --build-context docs=../../docs . -t discord_bot
```

All files in the docs folder are inserted into the db on startup.