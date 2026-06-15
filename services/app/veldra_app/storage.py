"""Object storage (MinIO / S3-compatible) for uploaded source documents."""

from __future__ import annotations

import asyncio
import functools

import boto3
from botocore.config import Config

from veldra_app.config import get_settings


@functools.lru_cache
def _s3_client():
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint_url,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        region_name=s.s3_region,
        config=Config(signature_version="s3v4"),
    )


def _put_sync(key: str, data: bytes, content_type: str) -> None:
    s = get_settings()
    _s3_client().put_object(Bucket=s.s3_bucket, Key=key, Body=data, ContentType=content_type)


def _get_sync(key: str) -> bytes:
    s = get_settings()
    return _s3_client().get_object(Bucket=s.s3_bucket, Key=key)["Body"].read()


async def put_object(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    await asyncio.to_thread(_put_sync, key, data, content_type)
    return key


async def get_object(key: str) -> bytes:
    return await asyncio.to_thread(_get_sync, key)
