from pathlib import Path

from shared_core.config.databento_config import DatabentoConfig
from shared_core.market_data.databento.client import DatabentoHistoricalClient
from shared_core.market_data.databento.request_limits import DatabentoSmokeRequest
from shared_core.storage import sha256_bytes


def test_databento_historical_client_fetches_tiny_raw_sample() -> None:
    fake_store = _FakeDBNStore(content=b"fake dbn zst bytes")
    fake_client = _FakeHistoricalClient(fake_store)
    request = DatabentoSmokeRequest.create()
    client = DatabentoHistoricalClient(
        DatabentoConfig(api_key="db-test-key"),
        historical_client=fake_client,
    )

    sample = client.get_raw_sample(request)

    assert fake_client.calls == [
        {
            "dataset": "EQUS.MINI",
            "symbols": "SPY",
            "schema": "ohlcv-1m",
            "start": "2024-01-02T14:30:00+00:00",
            "end": "2024-01-02T14:31:00+00:00",
            "stype_in": "raw_symbol",
            "limit": 1,
        }
    ]
    assert sample.content == b"fake dbn zst bytes"
    assert sample.content_hash == sha256_bytes(b"fake dbn zst bytes")
    assert sample.record_count == 1
    assert sample.raw_file_format == "dbn.zst"


class _FakeHistoricalClient:
    def __init__(self, store: "_FakeDBNStore") -> None:
        self.timeseries = self
        self.store = store
        self.calls: list[dict[str, object]] = []

    def get_range(self, **kwargs: object) -> "_FakeDBNStore":
        self.calls.append(kwargs)
        return self.store


class _FakeDBNStore:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def to_ndarray(self, *, schema: str, count: int | None = None) -> list[object]:
        assert schema == "ohlcv-1m"
        assert count is None
        return [object()]

    def to_file(self, path: str | Path) -> None:
        Path(path).write_bytes(self.content)
