"""Backtest run API routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.backtest_run import (
    BacktestRunResponse,
    DetectedSetupResponse,
    SimulatedTradeResponse,
)
from app.services.backtest_runs import (
    get_backtest_run,
    list_backtest_runs,
    list_detected_setups_for_backtest_run,
    list_simulated_trades_for_backtest_run,
)

router = APIRouter(prefix="/backtest-runs", tags=["backtest-runs"])
DbSession = Annotated[Session, Depends(get_db_session)]


@router.get("", response_model=list[BacktestRunResponse])
def list_backtest_run_metadata(
    session: DbSession,
    instrument_id: uuid.UUID | None = None,
    symbol: str | None = Query(default=None, min_length=1),
    run_status: str | None = Query(default=None, min_length=1),
    strategy_name: str | None = Query(default=None, min_length=1),
    timeframe: str | None = Query(default=None, min_length=1),
) -> list[BacktestRunResponse]:
    """List backtest run metadata."""

    return list_backtest_runs(
        session,
        instrument_id=instrument_id,
        symbol=symbol,
        run_status=run_status,
        strategy_name=strategy_name,
        timeframe=timeframe,
    )


@router.get("/{backtest_run_id}", response_model=BacktestRunResponse)
def get_backtest_run_metadata(
    backtest_run_id: uuid.UUID,
    session: DbSession,
) -> BacktestRunResponse:
    """Get one backtest run metadata record."""

    run = get_backtest_run(session, backtest_run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backtest run not found.",
        )
    return run


@router.get("/{backtest_run_id}/detected-setups", response_model=list[DetectedSetupResponse])
def list_backtest_run_detected_setups(
    backtest_run_id: uuid.UUID,
    session: DbSession,
) -> list[DetectedSetupResponse]:
    """List detected setups persisted for one backtest run."""

    if get_backtest_run(session, backtest_run_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backtest run not found.",
        )
    return list_detected_setups_for_backtest_run(session, backtest_run_id)


@router.get("/{backtest_run_id}/simulated-trades", response_model=list[SimulatedTradeResponse])
def list_backtest_run_simulated_trades(
    backtest_run_id: uuid.UUID,
    session: DbSession,
) -> list[SimulatedTradeResponse]:
    """List simulated trades persisted for one backtest run."""

    if get_backtest_run(session, backtest_run_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backtest run not found.",
        )
    return list_simulated_trades_for_backtest_run(session, backtest_run_id)
