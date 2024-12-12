from click.testing import CliRunner

from pgai.cli import vectorizer_worker


def run_vectorizer_worker(db_url: str, vectorizer_id: int) -> None:
    CliRunner().invoke(
        vectorizer_worker,
        [
            "--db-url",
            db_url,
            "--once",
            "--vectorizer-id",
            str(vectorizer_id),
            "--concurrency",
            "1",
        ],
        catch_exceptions=False,
    )
