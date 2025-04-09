import os
from dataclasses import dataclass
from io import BytesIO
from typing import Literal

from filetype import filetype  # type: ignore
from pydantic import BaseModel


@dataclass
class LoadedDocument:
    content: BytesIO
    file_path: str | None = None
    file_type: str | None = None


def guess_filetype(file_like: BytesIO, file_path: str | None = None) -> str | None:
    guess = filetype.guess(file_like)  # type: ignore
    file_like.seek(0)
    if guess is None:
        if file_path is None:
            return None
        return file_path.split(".")[-1]
    return guess.extension


class ColumnLoading(BaseModel):
    implementation: Literal["column"]
    column_name: str
    retries: int = 6

    def load(self, row: dict[str, str]) -> str | LoadedDocument:
        content = row[self.column_name] or ""
        if isinstance(content, bytes):
            content = BytesIO(content)
            return LoadedDocument(
                content=content,
                file_type=guess_filetype(content),
            )
        return content


class UriLoading(BaseModel):
    implementation: Literal["uri"]
    column_name: str
    retries: int = 6
    aws_role_arn: str | None = None

    def load(self, row: dict[str, str]) -> LoadedDocument:
        # Note: deferred import to avoid import overhead
        import boto3
        import smart_open  # type: ignore

        transport_params = None
        if self.aws_role_arn is not None:
            external_id = os.getenv("AWS_ASSUME_ROLE_EXTERNAL_ID")
            if external_id is not None:
                sts_client = boto3.client("sts")
                assumed_role = sts_client.assume_role(
                    RoleArn=self.aws_role_arn,
                    RoleSessionName="timescale-vectorizer",
                    ExternalId=external_id,
                )
                # Extract the temporary credentials
                credentials = assumed_role["Credentials"]

                # Create a boto3 session with the assumed role credentials
                session = boto3.Session(
                    aws_access_key_id=credentials["AccessKeyId"],
                    aws_secret_access_key=credentials["SecretAccessKey"],
                    aws_session_token=credentials["SessionToken"],
                )

                # Create an S3 client using the session with assumed role
                s3_client = session.client("s3")
                transport_params = {"client": s3_client}
        content = BytesIO(
            smart_open.open(
                row[self.column_name], "rb", transport_params=transport_params
            ).read()  # type: ignore
        )
        return LoadedDocument(
            content=content,
            file_path=row[self.column_name],
            file_type=guess_filetype(content, row[self.column_name]),
        )


class LoadingError(Exception):
    """
    Raised when the loader fails.
    """

    def __init__(self, *args: str, e: Exception):
        super().__init__(*args)
        self.__cause__ = e

    msg = "loading failed"
