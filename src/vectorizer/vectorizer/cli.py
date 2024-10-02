from argparse import ArgumentParser
from .__init__ import __version__


def run():
    parser = ArgumentParser(
        description="Process vectorizers to chunk and embed content"
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    args = parser.parse_args()

