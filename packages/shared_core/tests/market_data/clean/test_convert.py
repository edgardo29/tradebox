from datetime import UTC, datetime

from shared_core.market_data.clean.convert import convert_databento_ohlcv_records


def test_convert_databento_ohlcv_records_maps_prices_and_timestamps() -> None:
    processed_at = datetime(2026, 6, 28, 12, tzinfo=UTC)
    rows = convert_databento_ohlcv_records(
        [
            {
                "ts_event": 1_704_205_800_000_000_000,
                "open": 472_180_000_000,
                "high": 472_650_000_000,
                "low": 472_060_000_000,
                "close": 472_520_000_000,
                "volume": 47_609,
            }
        ],
        symbol="SPY",
        source_dataset="EQUS.MINI",
        source_schema="ohlcv-1m",
        timeframe="1m",
        processed_at=processed_at,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.symbol == "SPY"
    assert row.ts_event == datetime(2024, 1, 2, 14, 30, tzinfo=UTC)
    assert row.session_date.isoformat() == "2024-01-02"
    assert row.timeframe == "1m"
    assert row.open == 472.18
    assert row.high == 472.65
    assert row.low == 472.06
    assert row.close == 472.52
    assert row.volume == 47_609
    assert row.source_vendor == "databento"
    assert row.source_dataset == "EQUS.MINI"
    assert row.source_schema == "ohlcv-1m"
    assert row.processed_at == processed_at
