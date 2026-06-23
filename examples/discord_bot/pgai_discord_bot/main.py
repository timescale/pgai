import logging
import os
import re

import discord
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pgai.sqlalchemy import vectorizer_relationship
from sqlalchemy import Column, Integer, String, Text, func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, declarative_base, joinedload, mapped_column

load_dotenv()

# Create async engine
engine = create_async_engine(
    os.environ["DATABASE_URL"].replace("\n", ""), echo=True, future=True
)

async_session = async_sessionmaker(engine)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

Base = declarative_base()


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    file_name: Mapped[str] = mapped_column(String())
    content: Mapped[str] = mapped_column(Text())
    content_embeddings = vectorizer_relationship(
        dimensions=768,
    )


openai_client = AsyncOpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
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
            logger.info(
                "Query" + str(user_message)[:100] + "..."
                if len(str(user_message)) > 100
                else str(user_message)
            )
            logger.info(
                "Results:" + results[:200] + "..." if len(results) > 200 else results
            )
            return results


async def generate_rag_response(
    user_message: str, conversation_history: list[dict] = None
) -> str:
    """Generate a response using RAG pipeline.

    Args:
        user_message: The user's question
        conversation_history: Optional list of {"role": "user"|"assistant", "content": str} messages

    Returns:
        Generated response string
    """
    # Retrieve relevant documents
    relevant_docs = await retrieve_relevant_documents(user_message)

    # Generate response using OpenAI
    return await generate_response_with_docs(
        user_message, relevant_docs, conversation_history
    )


async def generate_response_with_docs(
    user_message: str, relevant_docs: str, conversation_history: list[dict] = None
) -> str:
    """Generate response using relevant docs and conversation history."""

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
        If you can't find anything useful, say so and tell the user to ask in a different channel. Other users or the development team may be able to help.
        """,
        "role": "system",
    }

    # Build messages list
    messages = [system_message]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"content": user_message, "role": "user"})

    chat_completion = await openai_client.chat.completions.create(
        messages=messages,
        model="gpt-4o",
    )
    return (
        chat_completion.choices[0].message.content
        or chat_completion.choices[0].message.refusal
    )  # type: ignore


async def ask_ai(
    bot: discord.ClientUser,
    previous_messages: list[discord.Message],
    relevant_docs: str,
) -> str:
    """Discord-specific wrapper for generate_response_with_docs."""
    # Convert Discord messages to conversation history format
    conversation_history = [
        {
            "content": message.content,
            "role": "assistant" if message.author == bot else "user",
            "name": re.sub(r"[^a-zA-Z0-9_-]", "_", message.author.name),
        }
        for message in previous_messages[:-1]  # Exclude the current message
    ]

    current_message = previous_messages[-1].content
    return await generate_response_with_docs(
        current_message, relevant_docs, conversation_history
    )


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
        """Check if we should process this message"""
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
