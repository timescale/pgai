from click.testing import CliRunner, Result

from pgai.cli import vectorizer_worker


def run_vectorizer_worker(
    db_url: str,
    vectorizer_id: int | None = None,
    concurrency: int = 1,
    extra_params: list[str] | None = None,
) -> Result:
    args = [
        "--db-url",
        db_url,
        "--once",
        "--concurrency",
        str(concurrency),
    ]
    if vectorizer_id is not None:
        args.extend(["--vectorizer-id", str(vectorizer_id)])
    if extra_params:
        args.extend(extra_params)

    return CliRunner().invoke(
        vectorizer_worker,
        args,
        catch_exceptions=False,
    )
