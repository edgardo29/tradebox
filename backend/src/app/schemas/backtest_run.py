"""Backtest run API schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class BacktestRunResponse(BaseModel):
    """API response shape for backtest run metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pipeline_run_id: uuid.UUID | None
    instrument_id: uuid.UUID
    instrument_symbol: str | None = None
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


class DetectedSetupResponse(BaseModel):
    """API response shape for persisted detected setups."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    backtest_run_id: uuid.UUID
    instrument_id: uuid.UUID
    data_partition_id: uuid.UUID | None
    setup_key: str
    setup_status: str
    side: str
    timeframe: str
    session_date: date
    detected_at: datetime
    setup_start_at: datetime | None
    setup_end_at: datetime | None
    triggered_at: datetime | None
    entry_price: Decimal | None
    stop_price: Decimal | None
    target_price: Decimal | None
    invalidation_price: Decimal | None
    setup_metadata_json: dict[str, Any]
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime


class SimulatedTradeResponse(BaseModel):
    """API response shape for persisted simulated trades."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    backtest_run_id: uuid.UUID
    detected_setup_id: uuid.UUID | None
    instrument_id: uuid.UUID
    trade_key: str
    trade_status: str
    side: str
    entry_at: datetime
    entry_price: Decimal
    exit_at: datetime | None
    exit_price: Decimal | None
    stop_price: Decimal | None
    target_price: Decimal | None
    quantity: Decimal | None
    risk_amount: Decimal | None
    gross_pnl: Decimal | None
    net_pnl: Decimal | None
    fees: Decimal | None
    slippage_amount: Decimal | None
    r_multiple: Decimal | None
    exit_reason: str | None
    trade_metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime
