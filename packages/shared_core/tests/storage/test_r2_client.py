from io import BytesIO

from shared_core.storage.r2_client import R2StorageClient
from shared_core.storage.r2_config import R2Config


def test_r2_client_reads_bytes_and_text() -> None:
    fake_client = _FakeS3Client(body=b"hello r2")
    client = R2StorageClient(_config(), s3_client=fake_client)

    assert client.read_bytes("sample.txt") == b"hello r2"
    assert client.read_text("sample.txt") == "hello r2"
    assert fake_client.get_object_calls == [
        {"Bucket": "tradebox-dev-market-data", "Key": "sample.txt"},
        {"Bucket": "tradebox-dev-market-data", "Key": "sample.txt"},
    ]


def test_r2_client_uploads_bytes() -> None:
    fake_client = _FakeS3Client(body=b"")
    client = R2StorageClient(_config(), s3_client=fake_client)

    client.upload_bytes("sample.dbn.zst", b"raw bytes", content_type="application/zstd")

    assert fake_client.put_object_calls == [
        {
            "Bucket": "tradebox-dev-market-data",
            "Key": "sample.dbn.zst",
            "Body": b"raw bytes",
            "ContentType": "application/zstd",
        }
    ]


def _config() -> R2Config:
    return R2Config(
        account_id="account",
        access_key_id="access",
        secret_access_key="secret",
        bucket_name="tradebox-dev-market-data",
        endpoint_url="https://account.r2.cloudflarestorage.com",
    )


class _FakeS3Client:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.get_object_calls: list[dict[str, str]] = []
        self.put_object_calls: list[dict[str, object]] = []

    def get_object(self, **kwargs: str) -> dict[str, BytesIO]:
        self.get_object_calls.append(kwargs)
        return {"Body": BytesIO(self.body)}

    def put_object(self, **kwargs: object) -> None:
        self.put_object_calls.append(kwargs)
