"""Small S3-compatible client for private Cloudflare R2 storage."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from shared_core.storage.object_keys import smoke_test_object_key
from shared_core.storage.r2_config import R2Config


@dataclass(frozen=True)
class R2SmokeTestResult:
    """Result metadata for a successful R2 smoke test."""

    bucket_name: str
    object_key: str


class R2StorageClient:
    """Minimal R2 client wrapper for object smoke tests and reusable storage calls."""

    def __init__(self, config: R2Config, s3_client: object | None = None) -> None:
        self.config = config
        self._client = s3_client if s3_client is not None else _build_boto3_client(config)

    def upload_text(self, key: str, text: str) -> None:
        self.upload_bytes(key, text.encode("utf-8"), content_type="text/plain; charset=utf-8")

    def upload_bytes(
        self,
        key: str,
        content: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> None:
        self._client.put_object(
            Bucket=self.config.bucket_name,
            Key=key,
            Body=content,
            ContentType=content_type,
        )

    def read_text(self, key: str) -> str:
        return self.read_bytes(key).decode("utf-8")

    def read_bytes(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self.config.bucket_name, Key=key)
        return response["Body"].read()

    def object_exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.config.bucket_name, Key=key)
        except Exception as exc:
            if _is_not_found_error(exc):
                return False
            raise
        return True

    def list_keys(self, prefix: str) -> list[str]:
        keys: list[str] = []
        continuation_token: str | None = None

        while True:
            request = {"Bucket": self.config.bucket_name, "Prefix": prefix}
            if continuation_token is not None:
                request["ContinuationToken"] = continuation_token

            response = self._client.list_objects_v2(**request)
            keys.extend(item["Key"] for item in response.get("Contents", []))

            if not response.get("IsTruncated"):
                return keys
            continuation_token = response.get("NextContinuationToken")

    def delete_object(self, key: str) -> None:
        self._client.delete_object(Bucket=self.config.bucket_name, Key=key)


def run_r2_smoke_test(config: R2Config) -> R2SmokeTestResult:
    """Upload, read, list, and delete a tiny private R2 object."""
    client = R2StorageClient(config)
    key = smoke_test_object_key(f"{uuid4().hex}.txt")
    expected_text = "tradebox r2 smoke test\n"

    try:
        client.upload_text(key, expected_text)
        if client.read_text(key) != expected_text:
            raise RuntimeError("R2 smoke test readback did not match uploaded text.")
        if not client.object_exists(key):
            raise RuntimeError("R2 smoke test object was not visible through head_object.")
        if key not in client.list_keys("dev/smoke-tests/"):
            raise RuntimeError("R2 smoke test object was not visible through list_objects_v2.")
    finally:
        client.delete_object(key)

    return R2SmokeTestResult(bucket_name=config.bucket_name, object_key=key)


def _build_boto3_client(config: R2Config) -> object:
    try:
        import boto3
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "boto3 is required for R2 access. Install the shared_core package dependencies."
        ) from exc

    return boto3.client(
        "s3",
        endpoint_url=config.s3_endpoint_url,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
        region_name="auto",
    )


def _is_not_found_error(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return False
    error = response.get("Error", {})
    return error.get("Code") in {"404", "NoSuchKey", "NotFound"}
