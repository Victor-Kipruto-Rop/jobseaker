"""Private S3-compatible object storage with local filesystem fallback."""
from __future__ import annotations
import re
from pathlib import Path
from uuid import uuid4
from apps.api.app.core.config import get_settings

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")

def _key(filename: str) -> str:
    name = Path(filename).name
    safe = _SAFE_NAME.sub("-", name).strip(".-")[:120] or "upload"
    return f"{uuid4().hex}/{safe}"

def store_private_object(content: bytes, filename: str, content_type: str) -> dict[str, str]:
    """Persist bytes privately and return an opaque object key, never a public URL."""
    if not content:
        raise ValueError("Cannot store an empty object")
    if len(content) > 25 * 1024 * 1024:
        raise ValueError("Object exceeds the 25 MiB upload limit")
    settings = get_settings()
    key = _key(filename)
    if settings.storage_backend == "s3":
        if not (settings.s3_access_key_id and settings.s3_secret_access_key):
            raise RuntimeError("S3 storage credentials are not configured")
        import boto3
        client = boto3.client(
            "s3", endpoint_url=settings.s3_endpoint_url, region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )
        kwargs = {"Bucket": settings.s3_bucket, "Key": key, "Body": content,
                  "ContentType": content_type or "application/octet-stream"}
        if not settings.s3_endpoint_url:
            kwargs["ServerSideEncryption"] = "AES256"
        client.put_object(**kwargs)
        return {"storage": "s3", "object_key": key}
    root = Path(settings.storage_path).resolve()
    destination = (root / key).resolve()
    if root not in destination.parents:
        raise ValueError("Invalid storage key")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    return {"storage": "local", "object_key": key}

def read_private_object(object_key: str) -> bytes:
    """Read an object using a server-controlled opaque key."""
    if not object_key or ".." in Path(object_key).parts or Path(object_key).is_absolute():
        raise ValueError("Invalid object key")
    settings = get_settings()
    if settings.storage_backend == "s3":
        import boto3
        client = boto3.client(
            "s3", endpoint_url=settings.s3_endpoint_url, region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )
        return client.get_object(Bucket=settings.s3_bucket, Key=object_key)["Body"].read()
    root = Path(settings.storage_path).resolve()
    path = (root / object_key).resolve()
    if root not in path.parents or not path.is_file():
        raise FileNotFoundError("Stored object not found")
    return path.read_bytes()
