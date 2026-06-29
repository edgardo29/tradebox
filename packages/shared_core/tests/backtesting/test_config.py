from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from shared_core.backtesting import BacktestConfig, BacktestConfigError

PARTITION_ID = UUID("11111111-2222-3333-4444-555555555555")


def test_backtest_config_validates_and_snapshots() -> None:
    config = BacktestConfig.create(
        symbol="spy",
        timeframe="1m",
        start=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
        end=datetime(2024, 1, 2, 14, 31, tzinfo=UTC),
        clean_data_partition_id=PARTITION_ID,
        strategy_name="noop",
        parameters={"example": True},
    )

    assert config.symbol == "SPY"
    assert config.strategy_config_hash()
    assert config.to_snapshot()["clean_data_partition_id"] == str(PARTITION_ID)
    assert config.to_snapshot()["parameters"] == {"example": True}


def test_backtest_config_rejects_invalid_date_range() -> None:
    start = datetime(2024, 1, 2, 14, 30, tzinfo=UTC)

    with pytest.raises(BacktestConfigError, match="start must be before end"):
        BacktestConfig.create(
            symbol="SPY",
            timeframe="1m",
            start=start,
            end=start,
            clean_data_partition_id=PARTITION_ID,
            strategy_name="noop",
        )


def test_backtest_config_rejects_broad_local_range() -> None:
    start = datetime(2024, 1, 2, tzinfo=UTC)

    with pytest.raises(BacktestConfigError, match="too broad"):
        BacktestConfig.create(
            symbol="SPY",
            timeframe="1m",
            start=start,
            end=start + timedelta(days=8),
            clean_data_partition_id=PARTITION_ID,
            strategy_name="noop",
        )


@pytest.mark.parametrize(
    ("field_name", "kwargs"),
    [
        ("symbol", {"symbol": ""}),
        ("timeframe", {"timeframe": ""}),
        ("strategy_name", {"strategy_name": ""}),
    ],
)
def test_backtest_config_rejects_required_strings(
    field_name: str,
    kwargs: dict[str, str],
) -> None:
    base = {
        "symbol": "SPY",
        "timeframe": "1m",
        "start": datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
        "end": datetime(2024, 1, 2, 14, 31, tzinfo=UTC),
        "clean_data_partition_id": PARTITION_ID,
        "strategy_name": "noop",
    }
    base.update(kwargs)

    with pytest.raises(BacktestConfigError, match=field_name):
        BacktestConfig.create(**base)


def test_backtest_config_rejects_missing_clean_partition_id() -> None:
    with pytest.raises(BacktestConfigError, match="clean data partition id"):
        BacktestConfig.create(
            symbol="SPY",
            timeframe="1m",
            start=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
            end=datetime(2024, 1, 2, 14, 31, tzinfo=UTC),
            clean_data_partition_id="not-a-uuid",
            strategy_name="noop",
        )
