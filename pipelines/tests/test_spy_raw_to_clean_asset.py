from __future__ import annotations

import pytest

from pipelines.assets import spy_raw_to_clean as asset_module
from pipelines.assets.spy_raw_to_clean import (
    ALLOW_LIVE_DATABENTO_ENV_VAR,
    live_databento_enabled,
    run_spy_raw_to_clean_workflow,
)


def test_live_databento_is_disabled_by_default() -> None:
    assert live_databento_enabled({}) is False
    assert live_databento_enabled({ALLOW_LIVE_DATABENTO_ENV_VAR: "false"}) is False
    assert live_databento_enabled({ALLOW_LIVE_DATABENTO_ENV_VAR: "0"}) is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_live_databento_requires_explicit_truthy_env(value: str) -> None:
    assert live_databento_enabled({ALLOW_LIVE_DATABENTO_ENV_VAR: value}) is True


def test_raw_to_clean_wrapper_calls_shared_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_workflow(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {
            "partition_id": "abc",
            "instrument_symbol": "SPY",
            "clean_object_path": "clean/path.parquet",
            "partition_status": "validated",
        }

    monkeypatch.setattr(asset_module, "raw_databento_partition_to_clean", fake_workflow)

    result = run_spy_raw_to_clean_workflow()

    assert result["instrument_symbol"] == "SPY"
    assert result["partition_status"] == "validated"
    assert calls == [{"symbol": "SPY"}]


def test_raw_to_clean_wrapper_raises_workflow_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_workflow(**_: object) -> dict[str, object]:
        raise RuntimeError("boom")

    monkeypatch.setattr(asset_module, "raw_databento_partition_to_clean", fake_workflow)

    with pytest.raises(RuntimeError, match="boom"):
        run_spy_raw_to_clean_workflow()
