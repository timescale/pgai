# Discord Bot

A minimal discord bot that answers questions based on pgai's documentation via RAG.
Built with python, py-cord, sqlalchemy and pgai.

## Running the Example

You will need a .env file with the following variables:

```shell
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost/postgres
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

The compose file by default also starts the bot container itself, if you want to run it locally for faster development you can do so by following the instructions below.

Install the python requirements with:
```shell
uv sync
```

To run the migrations to create necessary tables and setup the vectorizer run:
```shell
uv run alembic upgrade head
```

To populate the database with our docs run the insert_docs.py script with:
```shell
uv run python -m pgai_discord_bot.insert_docs
```

Afterwards you can run the bot with:

```shell
uv run python -m pgai_discord_bot.main
```

The bot will answer questions by creating threads and responding to them in the specified channel.

## Build the docker container
To build the docker container manually run:
```shell
docker build --build-context docs=../../docs . -t discord_bot
```

All files in the docs folder are inserted or updated in the db on startup.