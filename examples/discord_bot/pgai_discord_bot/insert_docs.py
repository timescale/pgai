import os
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from pgai_discord_bot.main import async_session, Document


async def process_markdown_files(
    directory_path: str | Path,
    async_session: AsyncSession,
    recursive: bool = True,
    excluded_dirs: list[str] | None = None,
) -> tuple[int, list[str]]:
    """
    Process all markdown files in a directory and insert them into the database.

    Args:
        directory_path: Path to the directory containing markdown files
        async_session: SQLAlchemy async session
        Document: Your SQLAlchemy Document model class
        recursive: Whether to search subdirectories
        excluded_dirs: List of directory names to exclude from search

    Returns:
        tuple containing:
            - Number of files processed
            - List of any files that failed to process
    """
    if excluded_dirs is None:
        excluded_dirs = [".git", "node_modules", "__pycache__"]

    processed_count = 0
    failed_files = []

    # Convert directory_path to Path object if it's a string
    base_path = Path(directory_path).resolve()

    if not base_path.exists():
        raise FileNotFoundError(f"Directory not found: {base_path}")

    async def process_file(file_path: Path) -> None:
        nonlocal processed_count
        try:
            # Create relative path for file_name
            relative_path = str(file_path.relative_to(base_path))

            # Check if document already exists
            existing_document = await async_session.execute(
                select(Document).where(Document.file_name == relative_path)
            )
            existing_document = existing_document.scalar_one_or_none()

            # Read the markdown file
            content = file_path.read_text(encoding="utf-8")

            if existing_document:
                # Update existing document if content has changed
                if existing_document.content != content:
                    existing_document.content = content
                    processed_count += 1
            else:
                # Create new document only if it doesn't exist
                document = Document(file_name=relative_path, content=content)
                async_session.add(document)
                processed_count += 1

        except Exception as e:
            failed_files.append(f"{file_path}: {str(e)}")

    # Walk through directory
    if recursive:
        for root, dirs, files in os.walk(base_path):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in excluded_dirs]

            for file in files:
                if file.endswith(".md"):
                    file_path = Path(root) / file
                    await process_file(file_path)
    else:
        # Only process files in the specified directory
        for file in base_path.glob("*.md"):
            await process_file(file)

    # Commit all changes
    try:
        await async_session.commit()
    except Exception as e:
        await async_session.rollback()
        raise Exception(f"Failed to commit changes to database: {str(e)}")

    return processed_count, failed_files


def get_docs_directory() -> Path:
    """
    Get the docs directory path from DOCS_PATH environment variable
    or fall back to docs directory next to script.
    """
    docs_env_path = os.getenv("DOCS_PATH")
    if docs_env_path:
        return Path(docs_env_path).resolve()

    # Fallback: navigate up three directories and into docs
    script_location = Path(__file__).resolve().parent
    docs_path = script_location.parent.parent.parent / "docs"
    return docs_path.resolve()


# Example usage:
async def main():
    docs_path = get_docs_directory()
    print(f"Processing markdown files in: {docs_path}")
    async with async_session() as session:
        processed, failed = await process_markdown_files(
            directory_path=docs_path,
            async_session=session,
            recursive=True,
            excluded_dirs=[".git"],
        )

        print(f"Processed {processed} files")
        if failed:
            print("Failed files:")
            for failure in failed:
                print(f"  - {failure}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
