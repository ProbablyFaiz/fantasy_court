import io
import urllib.parse
from pathlib import Path

import boto3
import rl.utils.io

BUCKET_NAME = rl.utils.io.getenv("FANTASY_COURT_BUCKET_NAME")
BUCKET_ACCESS_KEY_ID = rl.utils.io.getenv("FANTASY_COURT_BUCKET_ACCESS_KEY_ID")
BUCKET_SECRET_ACCESS_KEY = rl.utils.io.getenv("FANTASY_COURT_BUCKET_SECRET_ACCESS_KEY")
BUCKET_ENDPOINT = rl.utils.io.getenv("FANTASY_COURT_BUCKET_ENDPOINT")
BUCKET_REGION = rl.utils.io.getenv("FANTASY_COURT_BUCKET_REGION")
BUCKET_PUBLIC_URL = rl.utils.io.getenv("FANTASY_COURT_BUCKET_PUBLIC_URL")


def get_bucket_client() -> boto3.client:
    if any(
        v is None
        for v in (
            BUCKET_ACCESS_KEY_ID,
            BUCKET_SECRET_ACCESS_KEY,
            BUCKET_ENDPOINT,
            BUCKET_REGION,
        )
    ):
        raise ValueError("Missing bucket credentials")
    return boto3.client(
        "s3",
        aws_access_key_id=BUCKET_ACCESS_KEY_ID,
        aws_secret_access_key=BUCKET_SECRET_ACCESS_KEY,
        endpoint_url=BUCKET_ENDPOINT,
        region_name=BUCKET_REGION,
    )


def get_full_s3_path(path: str):
    return f"{BUCKET_NAME}/{path}"


def write_file(input_data: Path | bytes, s3_path: str, client: boto3.client) -> None:
    if isinstance(input_data, Path):
        with input_data.open("rb") as input_file:
            client.upload_fileobj(input_file, BUCKET_NAME, s3_path)
    else:  # input_data is bytes
        with io.BytesIO(input_data) as input_stream:
            client.upload_fileobj(input_stream, BUCKET_NAME, s3_path)


def read_file(s3_path: str, client: boto3.client) -> bytes:
    with io.BytesIO() as f:
        client.download_fileobj(BUCKET_NAME, s3_path, f)
        f.seek(0)
        return f.read()


def list_bucket_files(prefix: str, client: boto3.client) -> set[str]:
    paginator = client.get_paginator("list_objects_v2")
    result = set()
    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix):
        for content in page.get("Contents", []):
            result.add(content["Key"])
    return result


def get_signed_url(
    s3_path: str,
    client: boto3.client,
    *,
    download_file_name: str | None = None,
    ttl: int = 3600,
    verb: str = "get_object",
    inline: bool = False,
) -> str:
    """
    Get a presigned URL for a file in the bucket.

    Args:
        s3_path: The path to the file in the bucket.
        client: The boto3 client to use.
        download_file_name: The name of the file to download.
        ttl: The time to live for the presigned URL in seconds.
        verb: The HTTP verb to use for the presigned URL.
        inline: If True, set content disposition to inline for browser viewing.
                If False, set to attachment for download.

    Returns:
        A presigned URL for the file.
    """
    if download_file_name is None:
        download_file_name = s3_path.split("/")[-1]
    extra_params = {}
    if verb == "get_object":
        if inline:
            extra_params["ResponseContentDisposition"] = (
                f"inline; filename={urllib.parse.quote(download_file_name)}"
            )
        else:
            extra_params["ResponseContentDisposition"] = (
                f"attachment; filename={urllib.parse.quote(download_file_name)}"
            )
    url = client.generate_presigned_url(
        verb,
        Params={
            "Bucket": BUCKET_NAME,
            "Key": s3_path,
            **extra_params,
        },
        ExpiresIn=ttl,
    )
    return url


def get_public_url(s3_path: str) -> str:
    if not BUCKET_PUBLIC_URL:
        raise ValueError(
            "FANTASY_COURT_BUCKET_PUBLIC_URL is not set, but is required to get a public URL for a file in the bucket."
        )
    return f"{BUCKET_PUBLIC_URL.rstrip('/')}/{s3_path.lstrip('/')}"
