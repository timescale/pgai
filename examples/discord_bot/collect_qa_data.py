#!/usr/bin/env python3
"""
Script to collect top-level questions from Discord channel for pgai bot evaluation.
Extracts only the initial questions from threads for benchmarking.
"""

import asyncio
import json
import os
from datetime import datetime

import discord
from dotenv import load_dotenv

load_dotenv()


class QuestionCollector(discord.Client):
    def __init__(self, target_channel_id: int):
        self.target_channel_id = target_channel_id
        self.questions: list[str] = []
        self.collection_done = False

        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        super().__init__(intents=intents)

    async def on_ready(self):
        """Called when the bot is ready."""
        print(f"Logged in as {self.user}")
        await self.collect_questions()
        self.collection_done = True
        await self.close()

    async def collect_questions(self) -> list[str]:
        """Collect top-level questions from the Discord channel."""
        print("Collecting questions...")

        # Get the channel
        channel = None
        for guild in self.guilds:
            channel = guild.get_channel(self.target_channel_id)
            if channel:
                break

        if not channel:
            print(f"Channel {self.target_channel_id} not found")
            return []

        print(f"Collecting from channel: {channel.name}")

        if not isinstance(channel, discord.TextChannel):
            print("Channel is not a text channel")
            return []

        # Collect only messages that create threads (top-level questions)
        try:
            async for message in channel.history(limit=None):
                # Only collect messages that:
                # 1. Are not from bots
                # 2. Have content
                # 3. Have a thread (meaning they started a conversation)
                if (
                    not message.author.bot
                    and message.content.strip()
                    and message.thread is not None
                ):
                    self.questions.append(message.content.strip())
                    print(f"Found question: {message.content[:50]}...")
        except Exception as e:
            print(f"Error fetching channel messages: {e}")

        print(f"Collected {len(self.questions)} questions")
        return self.questions


async def main():
    """Main function to run the question collection."""
    bot_token = os.environ.get("DISCORD_BOT_TOKEN")
    if not bot_token:
        print("Error: DISCORD_BOT_TOKEN not found in environment")
        return

    channel_id = 1331981876319223879

    collector = QuestionCollector(channel_id)

    # Start the bot in a task
    bot_task = asyncio.create_task(collector.start(bot_token))

    # Wait for collection to complete with timeout
    start_time = asyncio.get_event_loop().time()
    timeout = 30  # 30 seconds timeout

    print("Waiting for collection to complete...")
    while not collector.collection_done:
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > timeout:
            print(f"Timeout after {timeout} seconds")
            collector.collection_done = True
            break
        await asyncio.sleep(1)

    # Cancel the bot task if it's still running
    if not bot_task.done():
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            pass

    questions = collector.questions

    if questions:
        # Save to JSON file
        output_file = (
            f"discord_questions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(questions, f, indent=2, ensure_ascii=False)

        print(f"Questions saved to {output_file}")
        print(f"Total questions collected: {len(questions)}")

        # Show first few questions
        print("\nFirst few questions:")
        for i, question in enumerate(questions[:5]):
            preview = question[:100] + "..." if len(question) > 100 else question
            print(f"{i+1}. {preview}")
    else:
        print("No questions collected")


if __name__ == "__main__":
    asyncio.run(main())
