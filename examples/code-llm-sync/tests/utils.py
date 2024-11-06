import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def wait_for_vectorizer(async_session: AsyncSession, timeout: int = 15) -> None:
    """Wait for vectorizer to process all pending items"""
    check_interval = 1  # second

    for _ in range(timeout):
        # Check if all files have embeddings
        result = await async_session.execute(
            text("""
            SELECT ai.vectorizer_queue_pending(1);
            """)
        )
        pending_count = result.scalar()

        if pending_count == 0:
            # All embeddings have been created
            return

        await asyncio.sleep(check_interval)

    raise TimeoutError("Vectorizer did not process items within expected timeframe")