from pydantic import BaseModel
from typing import Optional

StrategyId = str


class HoldingsItem(BaseModel):
    ticker: str
    name: str
    weight: float


class BacktestMetrics(BaseModel):
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    annual_volatility: Optional[float] = None
    turnover: Optional[float] = None
    period_start: str
    period_end: str
    absolute_return: Optional[float] = None
    # ── PMS extended metrics (populated when nav/benchmark data allows) ──
    relative_return: Optional[float] = None
    relative_return_geometric: Optional[float] = None
    weekly_return: Optional[float] = None
    monthly_return: Optional[float] = None
    quarterly_return: Optional[float] = None
    ytd_return: Optional[float] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None
    tracking_error: Optional[float] = None
    annual_tracking_error: Optional[float] = None
    information_ratio: Optional[float] = None
    daily_win_rate: Optional[float] = None
    weekly_win_rate: Optional[float] = None
    monthly_win_rate: Optional[float] = None
    calmar: Optional[float] = None
    avg_holding_days: Optional[float] = None


class SignalOverview(BaseModel):
    strategy_id: StrategyId
    strategy_name: str
    signal_date: str
    updated_at: Optional[str] = None
    holdings: list[HoldingsItem]
    signal_detail: dict


class SignalDetail(BaseModel):
    strategy_id: StrategyId
    strategy_name: str
    signal_date: str
    updated_at: Optional[str] = None
    holdings: list[HoldingsItem]
    signal_detail: dict
    nav_latest: Optional[float] = None
    metrics: Optional[BacktestMetrics] = None


class NavCurve(BaseModel):
    strategy_id: StrategyId
    dates: list[str]
    nav: list[float]
    benchmark_nav: Optional[list[float]] = None
    benchmark_name: Optional[str] = None
    excess_nav: Optional[list[float]] = None
    excess_name: Optional[str] = None


class SignalHistoryItem(BaseModel):
    date: str
    action: str
    detail: dict
