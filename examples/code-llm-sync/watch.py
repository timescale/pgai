import click
import asyncio
from pathlib import Path
import logging

from file_watcher import watch_directory


@click.command()
@click.option(
    "--path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=".",
    help="Directory to watch for changes",
)
@click.option(
    "--patterns",
    multiple=True,
    default=["*.py"],
    help="File patterns to watch (can be specified multiple times)",
)
@click.option(
    "--api-url",
    default="http://localhost:8000",
    help="Base URL of the API server",
)
@click.option(
    "--debounce",
    type=float,
    default=0.5,
    help="Debounce time in seconds",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose logging",
)
def watch(
        path: Path,
        patterns: list[str],
        api_url: str,
        debounce: float,
        verbose: bool,
) -> None:
    """Watch a directory for code changes and sync with the API server."""
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    async def run_watcher() -> None:
        try:
            watcher = await watch_directory(
                base_url=api_url,
                path=path,
                patterns=list(patterns),
                debounce_seconds=debounce,
            )

            # Keep running until interrupted
            while True:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            await watcher.stop()

    # Run the async watcher
    asyncio.run(run_watcher())

if __name__ == "__main__":
    watch()