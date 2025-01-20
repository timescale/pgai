import logging
import os
import re

from dotenv import load_dotenv
from sqlalchemy import Column, Integer, String, text, Text, select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, joinedload
import discord

from openai import AsyncOpenAI

from pgai.sqlalchemy import vectorizer_relationship

load_dotenv()

# Create async engine
engine = create_async_engine(os.environ["DATABASE_URL"], echo=True, future=True)

async_session = async_sessionmaker(engine)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

Base = declarative_base()


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    file_name = Column(String())
    content = Column(Text())
    content_embeddings = vectorizer_relationship(
        dimensions=768,
    )


openai_client = AsyncOpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),  # This is the default and can be omitted
)


async def retrieve_relevant_documents(user_message: str) -> str:
    async with async_session() as session:
        async with session.begin():
            statement = (
                select(Document.content_embeddings)
                .options(joinedload(Document.content_embeddings.parent))
                .order_by(  # type: ignore
                    Document.content_embeddings.embedding.cosine_distance(
                        func.ai.openai_embed(
                            "text-embedding-3-small",
                            user_message,
                            text("dimensions => 768"),
                        )
                    )
                )
                .limit(5)
            )
            result = await session.execute(statement)
            relevant_docs = result.scalars().all()  # type: ignore
            results = "\n".join(
                [f"{doc.parent.file_name}: {doc.chunk}" for doc in relevant_docs]
            )
            logger.info("Query", user_message)
            logger.info("Results:", results)
            return results


async def ask_ai(
    bot: discord.ClientUser,
    previous_messages: list[discord.Message],
    relevant_docs: str,
) -> str:
    logger.info("Responding with these docs:", relevant_docs)
    system_message = {
        "content": f"""
        You're the pgai documentation bot. Try to help the user with answering any questions about pgai based on this system message.
        pgai is a PostgreSQL extension that simplifies data storage and retrieval for Retrieval Augmented Generation (RAG), 
        and other AI applications. In particular, it automates the creation and sync of embeddings for your data stored in PostgreSQL,
        simplifies semantic search, and allows you to call LLM models from SQL.
        
        potentially relevant documentation based on the users question:
        {relevant_docs}
        
        Please try to keep answers concise this is a discord chat, the message cant be longer than 2000 characters.
        Also don't hallucinate code that wasn't mentioned in the documentation above! Only use APIs that are explicitly listed there.
        If you can't find anything useful, say so and tell the user to wait for a developer to respond (they have access to this chat).
        """,
        "role": "system",
    }

    chat_completion = await openai_client.chat.completions.create(
        messages=[system_message]
        + [  # type: ignore
            {
                "content": message.content,
                "role": "assistant" if message.author == bot else "user",
                "name": re.sub(r"[^a-zA-Z0-9_-]", "_", message.author.name),
            }
            for message in previous_messages  # type: ignore
        ],
        model="gpt-4o",
    )
    return (
        chat_completion.choices[0].message.content
        or chat_completion.choices[0].message.refusal
    )  # type: ignore


async def summarize_chat(chat: list[discord.Message], response: str) -> str:
    message = {
        "content": "Write a concise title for this chat history. Focus on what the user asks about."
        "Keep it shorter than 8 words \n"
        + "\n".join(
            [f"{message.author}: {message.content}" for message in chat] + [response]
        ),
        "role": "user",
    }
    chat_completion = await openai_client.chat.completions.create(
        messages=[message],  # type: ignore
        model="gpt-4o",
    )
    return (
        chat_completion.choices[0].message.content
        or chat_completion.choices[0].message.refusal
    )  # type: ignore


class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        # Get allowed channels from kwargs or use empty list
        self.channel_id: int = int(kwargs.pop("channel_id"))
        super().__init__(*args, **kwargs)

    async def check_message(
        self, message: discord.Message
    ) -> tuple[bool, discord.TextChannel | None]:
        """Check if we should process this message based on channel rules"""
        if message.author == self.user:
            return False, None

        # If message is in a thread, check its parent channel
        if isinstance(message.channel, discord.Thread):
            channel = message.channel.parent
        else:
            channel = message.channel
        # If message is in a regular channel, check the channel directly
        return (channel.id == self.channel_id), channel  # type: ignore

    async def on_ready(self):
        logger.info(f"Logged on as {self.user}!")

    async def on_message(self, message: discord.WebhookMessage):
        assert self.user is not None
        should_process_message, channel = await self.check_message(message)
        if not should_process_message:
            return
        assert channel is not None
        if isinstance(message.channel, discord.Thread):
            thread = message.channel
        elif message.thread:
            thread = message.thread
        else:
            thread = await message.create_thread(
                name=f"Discussion with {message.author.name}"
            )
        docs = await retrieve_relevant_documents(message.content)
        existing_messages = thread.history(limit=100, oldest_first=True)
        start_message: discord.Message = (
            thread.starting_message or await channel.fetch_message(thread.id)
        )
        messages = [start_message]
        async for thread_message in existing_messages:
            messages.append(thread_message)
        response = await ask_ai(self.user, messages, docs)
        await thread.send(response)
        if thread.name == "Discussion with " + message.author.name:
            title = await summarize_chat(messages, response)
            await thread.edit(name=title)


if __name__ == "__main__":
    intents = discord.Intents.default()
    intents.message_content = True

    client = MyClient(intents=intents, channel_id=os.environ["DISCORD_CHANNEL_ID"])
    client.run(os.environ["DISCORD_BOT_TOKEN"])
