import asyncio
import json
import os
from datetime import date, datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List

from app.models.signal_schema import SignalOverview, SignalDetail, NavCurve, BacktestMetrics, SignalHistoryItem
from app.services.generic_signal_parser import generic_signal_parser

router = APIRouter(prefix="/api/v1/signals", tags=["Strategy Signals"])


def _get_overview(strategy_id: str) -> SignalOverview | None:
    return generic_signal_parser.get_overview(strategy_id)


def _get_overviews() -> list[SignalOverview]:
    return generic_signal_parser.get_overviews()


def _get_detail(strategy_id: str) -> SignalDetail | None:
    return generic_signal_parser.get_detail(strategy_id)


def _get_history(strategy_id: str, limit: int = 30) -> list[SignalHistoryItem]:
    return generic_signal_parser.get_history(strategy_id, limit)


async def _save_signal_snapshot(overview: SignalOverview):
    try:
        from app.db.repository import save_signal
        holdings = [h.model_dump() for h in overview.holdings]
        await save_signal(
            strategy_id=overview.strategy_id,
            signal_date=overview.signal_date,
            holdings=holdings,
            detail=overview.signal_detail,
        )
    except Exception:
        pass


@router.get("/overview", response_model=List[SignalOverview])
async def get_all_overviews():
    overviews = _get_overviews()
    await asyncio.gather(*[_save_signal_snapshot(ov) for ov in overviews], return_exceptions=True)
    return overviews


@router.get("/overview/{strategy_id}", response_model=SignalOverview)
async def get_overview(strategy_id: str):
    result = _get_overview(strategy_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
    await _save_signal_snapshot(result)
    return result


@router.get("/detail/{strategy_id}", response_model=SignalDetail)
async def get_detail(strategy_id: str):
    result = _get_detail(strategy_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
    return result


@router.get("/nav/{strategy_id}", response_model=NavCurve)
async def get_nav(strategy_id: str):
    result = generic_signal_parser.get_nav(strategy_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"NAV data not found for {strategy_id}")
    return result


@router.get("/metrics/{strategy_id}", response_model=BacktestMetrics)
async def get_metrics(strategy_id: str):
    detail = generic_signal_parser.get_detail(strategy_id)
    if detail and detail.metrics:
        return detail.metrics
    raise HTTPException(status_code=404, detail=f"Metrics not available for {strategy_id}")


@router.get("/history/{strategy_id}", response_model=List[SignalHistoryItem])
async def get_history(strategy_id: str, limit: int = 30):
    # PG first
    try:
        from app.db.repository import load_signal_history
        rows = await load_signal_history(strategy_id, limit)
        if rows:
            items = []
            for row in rows:
                sd = row["signal_date"]
                holdings = row["holdings"]
                detail = row.get("signal_detail") or {}
                if isinstance(sd, date):
                    sd = str(sd)
                if isinstance(holdings, str):
                    holdings = json.loads(holdings)
                if isinstance(detail, str):
                    detail = json.loads(detail)
                items.append(SignalHistoryItem(
                    date=sd,
                    action=detail.get("action", "hold"),
                    detail={"holdings": holdings, **detail},
                ))
            return items
    except Exception:
        pass

    return _get_history(strategy_id, limit)


@router.get("/backtest/{strategy_id}")
async def get_backtest_window(strategy_id: str, start_date: str, end_date: str | None = None):
    """Recompute metrics for an arbitrary window of the strategy's nav series."""
    from app.services import generic_signal_parser as gsp

    data = generic_signal_parser.get_raw(strategy_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Strategy not found: {strategy_id}")
    nav_data = data.get("nav") or {}
    dates = nav_data.get("dates") or []
    values = nav_data.get("values") or []
    if len(dates) != len(values) or len(dates) < 2:
        raise HTTPException(status_code=404, detail=f"NAV data not found for {strategy_id}")

    lo = next((i for i, d in enumerate(dates) if d >= start_date), None)
    if lo is None:
        raise HTTPException(status_code=400, detail=f"start_date {start_date} is after last nav date {dates[-1]}")
    hi = len(dates) - 1
    if end_date:
        hi = next((len(dates) - 1 - k for k, d in enumerate(reversed(dates)) if d <= end_date), None)
        if hi is None:
            raise HTTPException(status_code=400, detail=f"end_date {end_date} is before first nav date {dates[0]}")
    if hi - lo < 1:
        raise HTTPException(status_code=400, detail="window contains fewer than 2 nav points")

    sliced = {"dates": dates[lo:hi + 1], "values": values[lo:hi + 1]}
    bench = nav_data.get("benchmark_nav")
    if bench and len(bench) == len(dates):
        sliced["benchmark_nav"] = bench[lo:hi + 1]
        sliced["benchmark_name"] = nav_data.get("benchmark_name")

    history_rows = [
        row for row in generic_signal_parser.get_raw_history(strategy_id)
        if str(row.get("date", "")) <= sliced["dates"][-1]
    ]
    metrics = gsp.compute_backtest_metrics(sliced, history_rows)
    if metrics is None:
        raise HTTPException(status_code=400, detail="window too narrow to compute metrics")

    from app.models.signal_schema import NavCurve
    window_curve = NavCurve(
        strategy_id=strategy_id,
        dates=sliced["dates"],
        nav=sliced["values"],
        benchmark_nav=sliced.get("benchmark_nav"),
        benchmark_name=sliced.get("benchmark_name"),
        excess_nav=None,
    )
    if window_curve.benchmark_nav:
        window_curve.excess_nav = gsp._excess_from_nav(
            [float(v) for v in window_curve.nav], [float(v) for v in window_curve.benchmark_nav]
        )
        window_curve.excess_name = "累计超额收益 (策略/基准 - 1)"
    return {"metrics": metrics, "nav": window_curve}
