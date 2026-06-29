"""Backtest run lifecycle workflows."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from shared_core.backtesting import BacktestConfig, BacktestRunResult
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.models import BacktestRun, DataPartition, DetectedSetup, Instrument, SimulatedTrade

BACKTEST_STATUS_PENDING = "pending"
BACKTEST_STATUS_RUNNING = "running"
BACKTEST_STATUS_SUCCEEDED = "succeeded"
BACKTEST_STATUS_FAILED = "failed"
VALID_CLEAN_PARTITION_STATUSES = {"clean_available", "validated"}


class BacktestInputPartitionError(ValueError):
    """Raised when a data partition is not usable as backtest input."""


class BacktestResultPersistenceError(ValueError):
    """Raised when a result cannot be persisted by the current foundation."""


@dataclass(frozen=True)
class BacktestRunMetadata:
    """API-facing backtest run metadata with instrument symbol."""

    id: uuid.UUID
    pipeline_run_id: uuid.UUID | None
    instrument_id: uuid.UUID
    instrument_symbol: str | None
    run_status: str
    strategy_name: str
    strategy_version: str
    strategy_config_hash: str
    timeframe: str
    start_date: date
    end_date: date
    parameters_json: dict[str, Any]
    execution_assumptions_json: dict[str, Any]
    input_data_snapshot_json: dict[str, Any]
    metrics_json: dict[str, Any]
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


def create_backtest_run_from_config(
    session: Session,
    *,
    instrument_id: uuid.UUID,
    config: BacktestConfig,
    input_data_snapshot: dict[str, Any],
    pipeline_run_id: uuid.UUID | None = None,
    execution_assumptions: dict[str, Any] | None = None,
    commit: bool = False,
) -> BacktestRun:
    """Create a pending backtest run from a validated shared_core config."""

    run = BacktestRun(
        pipeline_run_id=pipeline_run_id,
        instrument_id=instrument_id,
        run_status=BACKTEST_STATUS_PENDING,
        strategy_name=config.strategy_name,
        strategy_version=config.strategy_version,
        strategy_config_hash=config.strategy_config_hash(),
        timeframe=config.timeframe,
        start_date=config.start.date(),
        end_date=config.end.date(),
        parameters_json=config.to_snapshot(),
        execution_assumptions_json=execution_assumptions or {},
        input_data_snapshot_json=input_data_snapshot,
        metrics_json={},
    )
    session.add(run)
    session.flush()
    if commit:
        session.commit()
        session.refresh(run)
    return run


def mark_backtest_run_running(
    session: Session,
    run: BacktestRun,
    *,
    commit: bool = False,
) -> BacktestRun:
    """Mark a backtest run as running."""

    run.run_status = BACKTEST_STATUS_RUNNING
    run.started_at = datetime.now(UTC)
    run.error_message = None
    session.flush()
    if commit:
        session.commit()
        session.refresh(run)
    return run


def write_backtest_results(
    session: Session,
    run: BacktestRun,
    result: BacktestRunResult,
    *,
    commit: bool = False,
) -> dict[str, int]:
    """Persist setup/trade result rows and update aggregate run metrics."""

    if run.detected_setups or run.simulated_trades:
        raise BacktestResultPersistenceError("Backtest results have already been persisted.")

    setup_by_key: dict[str, DetectedSetup] = {}
    for payload in result.detected_setups:
        setup = _detected_setup_from_payload(run, payload)
        if setup.setup_key in setup_by_key:
            raise BacktestResultPersistenceError(
                f"Duplicate detected setup key: {setup.setup_key}."
            )
        setup_by_key[setup.setup_key] = setup
    trade_rows = [
        _simulated_trade_from_payload(run, payload, setup_by_key)
        for payload in result.simulated_trades
    ]
    session.add_all([*setup_by_key.values(), *trade_rows])
    counts = {
        "detected_setup_count": len(setup_by_key),
        "simulated_trade_count": len(trade_rows),
    }
    run.metrics_json = {
        **run.metrics_json,
        **result.metrics,
        **counts,
    }
    session.flush()
    if commit:
        session.commit()
        session.refresh(run)
    return counts


def list_detected_setups_for_backtest_run(
    session: Session,
    backtest_run_id: uuid.UUID,
) -> list[DetectedSetup]:
    """List detected setup rows for a backtest run."""

    statement = (
        select(DetectedSetup)
        .where(DetectedSetup.backtest_run_id == backtest_run_id)
        .order_by(DetectedSetup.detected_at, DetectedSetup.setup_key)
    )
    return list(session.scalars(statement).all())


def list_simulated_trades_for_backtest_run(
    session: Session,
    backtest_run_id: uuid.UUID,
) -> list[SimulatedTrade]:
    """List simulated trade rows for a backtest run."""

    statement = (
        select(SimulatedTrade)
        .where(SimulatedTrade.backtest_run_id == backtest_run_id)
        .order_by(SimulatedTrade.entry_at, SimulatedTrade.trade_key)
    )
    return list(session.scalars(statement).all())


def mark_backtest_run_succeeded(
    session: Session,
    run: BacktestRun,
    result: BacktestRunResult,
    *,
    commit: bool = False,
) -> BacktestRun:
    """Mark a backtest run as succeeded with metrics."""

    run.run_status = BACKTEST_STATUS_SUCCEEDED
    run.metrics_json = {
        **run.metrics_json,
        **result.metrics,
        "run_status": result.run_status,
        "candle_count": result.candle_count,
        "detected_setup_count": result.detected_setup_count,
        "simulated_trade_count": result.simulated_trade_count,
    }
    run.error_message = None
    run.finished_at = datetime.now(UTC)
    session.flush()
    if commit:
        session.commit()
        session.refresh(run)
    return run


def mark_backtest_run_failed(
    session: Session,
    run: BacktestRun,
    *,
    error_message: str,
    commit: bool = False,
) -> BacktestRun:
    """Mark a backtest run as failed and store an error message."""

    run.run_status = BACKTEST_STATUS_FAILED
    run.error_message = error_message
    run.finished_at = datetime.now(UTC)
    session.flush()
    if commit:
        session.commit()
        session.refresh(run)
    return run


def build_backtest_input_snapshot(partition: DataPartition) -> dict[str, Any]:
    """Validate a clean data partition and return a reproducible input snapshot."""

    if not partition.clean_object_path:
        raise BacktestInputPartitionError("Backtest input partition is missing clean_object_path.")
    if partition.partition_status not in VALID_CLEAN_PARTITION_STATUSES:
        raise BacktestInputPartitionError("Backtest input partition must be clean or validated.")
    if partition.clean_file_format != "parquet":
        raise BacktestInputPartitionError("Backtest input partition must reference Parquet data.")

    return {
        "data_partition_id": str(partition.id),
        "instrument_id": str(partition.instrument_id),
        "vendor": partition.vendor,
        "dataset": partition.dataset,
        "timeframe": partition.timeframe,
        "session_date": partition.session_date.isoformat(),
        "clean_object_path": partition.clean_object_path,
        "clean_file_format": partition.clean_file_format,
        "clean_content_hash": partition.clean_content_hash,
        "row_count": partition.row_count,
        "partition_status": partition.partition_status,
    }


def list_backtest_runs(
    session: Session,
    *,
    instrument_id: uuid.UUID | None = None,
    symbol: str | None = None,
    run_status: str | None = None,
    strategy_name: str | None = None,
    timeframe: str | None = None,
) -> list[BacktestRunMetadata]:
    """List backtest run metadata with optional filters."""

    statement = select(BacktestRun, Instrument.symbol).join(
        Instrument,
        BacktestRun.instrument_id == Instrument.id,
    )
    statement = _apply_filters(
        statement,
        instrument_id=instrument_id,
        symbol=symbol,
        run_status=run_status,
        strategy_name=strategy_name,
        timeframe=timeframe,
    )
    statement = statement.order_by(BacktestRun.created_at.desc())
    return [_to_metadata(run, symbol) for run, symbol in session.execute(statement).all()]


def get_backtest_run(session: Session, backtest_run_id: uuid.UUID) -> BacktestRunMetadata | None:
    """Get one backtest run by id."""

    statement = (
        select(BacktestRun, Instrument.symbol)
        .join(Instrument, BacktestRun.instrument_id == Instrument.id)
        .where(BacktestRun.id == backtest_run_id)
    )
    row = session.execute(statement).one_or_none()
    if row is None:
        return None
    run, symbol = row
    return _to_metadata(run, symbol)


def _detected_setup_from_payload(
    run: BacktestRun,
    payload: Mapping[str, Any],
) -> DetectedSetup:
    detected_at = _required_datetime(payload, "detected_at", "detected setup")
    return DetectedSetup(
        backtest_run_id=run.id,
        instrument_id=run.instrument_id,
        data_partition_id=_optional_uuid(
            payload.get("data_partition_id", _run_data_partition_id(run)),
            "data_partition_id",
            "detected setup",
        ),
        setup_key=_required_str(payload, "setup_key", "detected setup"),
        setup_status=_optional_str(payload, "setup_status") or "detected",
        side=_required_str(payload, "side", "detected setup"),
        timeframe=_optional_str(payload, "timeframe") or run.timeframe,
        session_date=_optional_date(payload.get("session_date"), "session_date", "detected setup")
        or detected_at.date(),
        detected_at=detected_at,
        setup_start_at=_optional_datetime(
            payload.get("setup_start_at"), "setup_start_at", "detected setup"
        ),
        setup_end_at=_optional_datetime(
            payload.get("setup_end_at"), "setup_end_at", "detected setup"
        ),
        triggered_at=_optional_datetime(
            payload.get("triggered_at"), "triggered_at", "detected setup"
        ),
        entry_price=_optional_decimal(payload.get("entry_price"), "entry_price", "detected setup"),
        stop_price=_optional_decimal(payload.get("stop_price"), "stop_price", "detected setup"),
        target_price=_optional_decimal(
            payload.get("target_price"), "target_price", "detected setup"
        ),
        invalidation_price=_optional_decimal(
            payload.get("invalidation_price"), "invalidation_price", "detected setup"
        ),
        setup_metadata_json=_metadata_json(payload, "setup_metadata_json"),
        rejection_reason=_optional_str(payload, "rejection_reason"),
    )


def _simulated_trade_from_payload(
    run: BacktestRun,
    payload: Mapping[str, Any],
    setup_by_key: Mapping[str, DetectedSetup],
) -> SimulatedTrade:
    setup = None
    detected_setup_id = _optional_uuid(
        payload.get("detected_setup_id"), "detected_setup_id", "simulated trade"
    )
    detected_setup_key = _optional_str(payload, "detected_setup_key")
    if detected_setup_key is not None and detected_setup_id is None:
        setup = setup_by_key.get(detected_setup_key)
        if setup is None:
            raise BacktestResultPersistenceError(
                f"Unknown detected setup key for simulated trade: {detected_setup_key}."
            )

    return SimulatedTrade(
        backtest_run_id=run.id,
        detected_setup_id=detected_setup_id,
        detected_setup=setup,
        instrument_id=run.instrument_id,
        trade_key=_required_str(payload, "trade_key", "simulated trade"),
        trade_status=_optional_str(payload, "trade_status") or "open",
        side=_required_str(payload, "side", "simulated trade"),
        entry_at=_required_datetime(payload, "entry_at", "simulated trade"),
        entry_price=_required_decimal(payload, "entry_price", "simulated trade"),
        exit_at=_optional_datetime(payload.get("exit_at"), "exit_at", "simulated trade"),
        exit_price=_optional_decimal(payload.get("exit_price"), "exit_price", "simulated trade"),
        stop_price=_optional_decimal(payload.get("stop_price"), "stop_price", "simulated trade"),
        target_price=_optional_decimal(
            payload.get("target_price"), "target_price", "simulated trade"
        ),
        quantity=_optional_decimal(payload.get("quantity"), "quantity", "simulated trade"),
        risk_amount=_optional_decimal(
            payload.get("risk_amount"), "risk_amount", "simulated trade"
        ),
        gross_pnl=_optional_decimal(payload.get("gross_pnl"), "gross_pnl", "simulated trade"),
        net_pnl=_optional_decimal(payload.get("net_pnl"), "net_pnl", "simulated trade"),
        fees=_optional_decimal(payload.get("fees"), "fees", "simulated trade"),
        slippage_amount=_optional_decimal(
            payload.get("slippage_amount"), "slippage_amount", "simulated trade"
        ),
        r_multiple=_optional_decimal(payload.get("r_multiple"), "r_multiple", "simulated trade"),
        exit_reason=_optional_str(payload, "exit_reason"),
        trade_metadata_json=_metadata_json(payload, "trade_metadata_json"),
    )


def _run_data_partition_id(run: BacktestRun) -> str | None:
    value = run.input_data_snapshot_json.get("data_partition_id")
    if value is None:
        return None
    return str(value)


def _required_str(payload: Mapping[str, Any], field_name: str, result_type: str) -> str:
    value = _optional_str(payload, field_name)
    if value is None:
        raise BacktestResultPersistenceError(f"{result_type} requires {field_name}.")
    return value


def _optional_str(payload: Mapping[str, Any], field_name: str) -> str | None:
    value = payload.get(field_name)
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _required_datetime(
    payload: Mapping[str, Any],
    field_name: str,
    result_type: str,
) -> datetime:
    value = _optional_datetime(payload.get(field_name), field_name, result_type)
    if value is None:
        raise BacktestResultPersistenceError(f"{result_type} requires {field_name}.")
    return value


def _optional_datetime(value: Any, field_name: str, result_type: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise BacktestResultPersistenceError(
                f"{result_type} {field_name} must be an ISO datetime."
            ) from exc
    else:
        raise BacktestResultPersistenceError(f"{result_type} {field_name} must be a datetime.")

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _optional_date(value: Any, field_name: str, result_type: str) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise BacktestResultPersistenceError(
                f"{result_type} {field_name} must be an ISO date."
            ) from exc
    raise BacktestResultPersistenceError(f"{result_type} {field_name} must be a date.")


def _required_decimal(payload: Mapping[str, Any], field_name: str, result_type: str) -> Decimal:
    value = _optional_decimal(payload.get(field_name), field_name, result_type)
    if value is None:
        raise BacktestResultPersistenceError(f"{result_type} requires {field_name}.")
    return value


def _optional_decimal(value: Any, field_name: str, result_type: str) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise BacktestResultPersistenceError(
            f"{result_type} {field_name} must be decimal-like."
        ) from exc


def _optional_uuid(value: Any, field_name: str, result_type: str) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise BacktestResultPersistenceError(f"{result_type} {field_name} must be a UUID.") from exc


def _metadata_json(payload: Mapping[str, Any], field_name: str) -> dict[str, Any]:
    value = payload.get(field_name, payload.get("metadata", {}))
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise BacktestResultPersistenceError(f"{field_name} must be an object.")
    return dict(value)


def _apply_filters(
    statement: Select[tuple[BacktestRun, str]],
    *,
    instrument_id: uuid.UUID | None,
    symbol: str | None,
    run_status: str | None,
    strategy_name: str | None,
    timeframe: str | None,
) -> Select[tuple[BacktestRun, str]]:
    if instrument_id is not None:
        statement = statement.where(BacktestRun.instrument_id == instrument_id)
    if symbol is not None:
        statement = statement.where(Instrument.symbol == symbol.upper())
    if run_status is not None:
        statement = statement.where(BacktestRun.run_status == run_status)
    if strategy_name is not None:
        statement = statement.where(BacktestRun.strategy_name == strategy_name)
    if timeframe is not None:
        statement = statement.where(BacktestRun.timeframe == timeframe)
    return statement


def _to_metadata(run: BacktestRun, instrument_symbol: str | None) -> BacktestRunMetadata:
    return BacktestRunMetadata(
        id=run.id,
        pipeline_run_id=run.pipeline_run_id,
        instrument_id=run.instrument_id,
        instrument_symbol=instrument_symbol,
        run_status=run.run_status,
        strategy_name=run.strategy_name,
        strategy_version=run.strategy_version,
        strategy_config_hash=run.strategy_config_hash,
        timeframe=run.timeframe,
        start_date=run.start_date,
        end_date=run.end_date,
        parameters_json=run.parameters_json,
        execution_assumptions_json=run.execution_assumptions_json,
        input_data_snapshot_json=run.input_data_snapshot_json,
        metrics_json=run.metrics_json,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error_message=run.error_message,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )
