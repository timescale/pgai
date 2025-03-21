#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "datasets",
#     "huggingface_hub",
# ]
# ///
import argparse
import logging
import os
import re
from datetime import datetime, timezone
from glob import glob
from pathlib import Path

import datasets
import huggingface_hub

REPO_ROOT = Path(__file__).parent.parent.absolute()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_file_content(file_path: str) -> str:
    """Get the content of a file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.warning(f"Error reading file {file_path}: {e}")
        return ""


def doc_file_generator():
    for file in glob(f"{REPO_ROOT}/docs/**/*.md"):
        logger.info(f"Loading file {file}")
        path = os.path.relpath(file, REPO_ROOT)
        contents = get_file_content(file)
        result = re.search("^# (.*)$", contents, re.MULTILINE)
        if result is None:
            raise RuntimeError(f"No title found for file {path}")
        else:
            title = result.group(1)
        yield {"path": path, "title": title, "contents": contents}


def check_huggingface_dataset():
    logger.info("Starting check")
    for _ in doc_file_generator():
        pass
    logger.info("Done")


def push_huggingface_dataset():
    logger.info("Starting push")
    features = datasets.Features(
        {
            "path": datasets.Value(dtype="string", id=None),
            "title": datasets.Value(dtype="string", id=None),
            "contents": datasets.Value(dtype="string", id=None),
        }
    )
    ds = datasets.Dataset.from_generator(doc_file_generator, features=features)
    logger.info("Logging in to huggingface hub")
    token = os.getenv("HUGGINGFACE_HUB_TIMESCALE_TOKEN")
    huggingface_hub.login(token)
    logger.info("Pushing dataset to huggingface hub")
    timestamp = datetime.now(timezone.utc)
    commit_message = f"Docs update {timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")}"
    ds.push_to_hub("timescale/pgai-docs", commit_message=commit_message)
    logger.info("Done")


def parse_args():
    parser = argparse.ArgumentParser(description="Huggingface docs dataset generator")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    subparsers.add_parser("check", help="Check docs dataset")
    subparsers.add_parser("push", help="Push docs dataset")
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        exit(1)
    return args


def main():
    args = parse_args()
    match args.command:
        case "check":
            check_huggingface_dataset()
        case "push":
            push_huggingface_dataset()


if __name__ == "__main__":
    main()
