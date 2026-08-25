"""PMS-style 22-metric backtest calculator (generic, benchmark optional).

Conventions: NAV inputs must be normalised to 1.0 at the first common date.
Returns None for any metric whose sample is too small or variance is zero —
never fabricates 0. Without a benchmark, relative metrics (relative return,
alpha/beta, tracking error, information ratio) stay None.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import math
import numpy as np
import pandas as pd


_RISK_FREE_ANNUAL = 0.015  # 1.5% annualised, per plan


@dataclass
class PMSResult:
    """22 PMS metrics. None means the metric cannot be computed reliably."""

    absolute_return: Optional[float] = None
    relative_return: Optional[float] = None
    relative_return_geometric: Optional[float] = None
    weekly_return: Optional[float] = None
    monthly_return: Optional[float] = None
    quarterly_return: Optional[float] = None
    ytd_return: Optional[float] = None
    annual_return: Optional[float] = None
    annual_volatility: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None
    tracking_error: Optional[float] = None
    annual_tracking_error: Optional[float] = None
    information_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    daily_win_rate: Optional[float] = None
    weekly_win_rate: Optional[float] = None
    monthly_win_rate: Optional[float] = None
    calmar: Optional[float] = None
    turnover: Optional[float] = None
    avg_holding_days: Optional[float] = None
    # extra metadata
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    n_trading_days: Optional[int] = None

    def to_metrics_dict(self) -> dict:
        """Translate to BacktestMetrics-compatible dict (compatible with old schema)."""
        # Old required fields — derive from new fields so legacy parsers don't break.
        annual_return = self.annual_return if self.annual_return is not None else 0.0
        max_drawdown = self.max_drawdown if self.max_drawdown is not None else 0.0
        sharpe = self.sharpe_ratio if self.sharpe_ratio is not None else 0.0
        win_rate = self.daily_win_rate if self.daily_win_rate is not None else 0.0
        return {
            "annual_return": float(annual_return),
            "max_drawdown": float(max_drawdown),
            "sharpe_ratio": float(sharpe),
            "win_rate": float(win_rate),
            "absolute_return": _safe_float(self.absolute_return),
            "annual_volatility": _safe_float(self.annual_volatility),
            "turnover": _safe_float(self.turnover),
            "period_start": self.period_start or "",
            "period_end": self.period_end or "",
            # PMS extended
            "relative_return": _safe_float(self.relative_return),
            "relative_return_geometric": _safe_float(self.relative_return_geometric),
            "weekly_return": _safe_float(self.weekly_return),
            "monthly_return": _safe_float(self.monthly_return),
            "quarterly_return": _safe_float(self.quarterly_return),
            "ytd_return": _safe_float(self.ytd_return),
            "alpha": _safe_float(self.alpha),
            "beta": _safe_float(self.beta),
            "tracking_error": _safe_float(self.tracking_error),
            "annual_tracking_error": _safe_float(self.annual_tracking_error),
            "information_ratio": _safe_float(self.information_ratio),
            "daily_win_rate": _safe_float(self.daily_win_rate),
            "weekly_win_rate": _safe_float(self.weekly_win_rate),
            "monthly_win_rate": _safe_float(self.monthly_win_rate),
            "calmar": _safe_float(self.calmar),
            "avg_holding_days": _safe_float(self.avg_holding_days),
        }


@dataclass
class SubStrategyTurnover:
    """Inputs needed to compute turnover and avg holding days for one sub-strategy."""

    name: str
    build_weight: float  # 在组合里占的初始资金份额，例如 0.428571
    # 权重历史：index=trade_date, columns=tickers, values=该子账户内部 weight（每个子账户内权重和=1）
    weight_history: Optional[pd.DataFrame] = None
    # Cash participates in turnover but is not a security holding-duration segment.
    cash_columns: frozenset[str] = field(default_factory=frozenset)


def _safe_float(x) -> Optional[float]:
    if x is None:
        return None
    try:
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def _ols_alpha_beta(strategy_ret: np.ndarray, bench_ret: np.ndarray) -> tuple[Optional[float], Optional[float]]:
    """Plain OLS with intercept. Returns (alpha_daily, beta). None if degenerate."""
    if len(strategy_ret) < 5 or len(bench_ret) < 5:
        return None, None
    x = bench_ret.astype(float)
    y = strategy_ret.astype(float)
    if np.std(x) == 0 or np.std(y) == 0:
        # Zero variance in either side → no meaningful regression
        return None, None
    x_mean = x.mean()
    y_mean = y.mean()
    cov = ((x - x_mean) * (y - y_mean)).sum()
    var = ((x - x_mean) ** 2).sum()
    if var == 0:
        return None, None
    beta = float(cov / var)
    alpha = float(y_mean - beta * x_mean)
    return alpha, beta


def _max_drawdown(nav: np.ndarray) -> Optional[float]:
    if len(nav) < 2:
        return None
    peak = np.maximum.accumulate(nav)
    dd = (nav - peak) / peak
    return float(np.min(dd))


def _period_return(nav_series: pd.Series, start_date: pd.Timestamp, end_date: pd.Timestamp) -> Optional[float]:
    """Strategy return from the first common trade day >= start_date through end_date."""
    if nav_series.empty:
        return None
    sub = nav_series.loc[(nav_series.index >= start_date) & (nav_series.index <= end_date)]
    if len(sub) < 2:
        return None
    return float(sub.iloc[-1] / sub.iloc[0] - 1)


def _resample_returns(nav_series: pd.Series, rule: str) -> pd.Series:
    """Resample NAV to weekly/monthly then take pct_change. Drops NaN."""
    if nav_series.empty:
        return pd.Series(dtype=float)
    s = nav_series.resample(rule).last().dropna()
    return s.pct_change().dropna()


def compute_pms_metrics(
    strategy_nav: pd.Series,
    benchmark_nav: pd.Series | None = None,
    sub_strategies: list[SubStrategyTurnover] | None = None,
    period_end: pd.Timestamp | None = None,
) -> PMSResult:
    """Compute the 22 PMS metrics. Inputs MUST be normalised to 1.0 at build_date.

    Args:
        strategy_nav: pd.Series, index=trade_date (Timestamp), values=NAV (1.0 at build_date)
        benchmark_nav: pd.Series | None, same convention; None skips relative metrics
        sub_strategies: list of SubStrategyTurnover for turnover/avg_holding_days computation
        period_end: cutoff date; defaults to last common trade date
    """
    res = PMSResult()

    # Inner join on common trade dates
    frames = [strategy_nav.rename("s")]
    if benchmark_nav is not None:
        frames.append(benchmark_nav.rename("b"))
    df = pd.concat(frames, axis=1).dropna()
    if len(df) < 2:
        return res

    if period_end is None:
        period_end = df.index[-1]
    df = df.loc[df.index <= period_end]

    if len(df) < 2:
        return res

    s_nav = df["s"]
    b_nav = df["b"] if "b" in df.columns else None
    s_ret = s_nav.pct_change().dropna()
    b_ret = b_nav.pct_change().dropna() if b_nav is not None else None
    excess_ret = (s_ret - b_ret).dropna() if b_ret is not None else None

    n_days = len(df)
    res.period_start = s_nav.index[0].strftime("%Y-%m-%d")
    res.period_end = s_nav.index[-1].strftime("%Y-%m-%d")
    res.n_trading_days = n_days

    # ── 1. 绝对回报 ──
    res.absolute_return = float(s_nav.iloc[-1] - 1)

    # ── 2. 相对回报（算术）──
    # ── 3. 几何相对回报 ──
    if b_nav is not None:
        s_total = float(s_nav.iloc[-1] / s_nav.iloc[0] - 1)
        b_total = float(b_nav.iloc[-1] / b_nav.iloc[0] - 1)
        res.relative_return = s_total - b_total

        if b_nav.iloc[-1] > 0 and b_nav.iloc[0] > 0:
            res.relative_return_geometric = float(s_nav.iloc[-1] / b_nav.iloc[-1] - 1)

    # ── 4-7. 周/月/季/年回报 ──
    end = s_nav.index[-1]
    # Week: 上周五收盘 → end (用户视角"一周收益": 上周最后交易日收盘 → end).
    # 不用 ISO 周一当起点 — 那样会漏掉本周一相对上周五的跳空跌幅, 导致 weekly_return
    # 与"5 交易日累计涨跌"对不上. 用 <= prev_friday 的最后一个交易日作基准,
    # 避免 prev_friday 是节假日时把起点推到本周.
    prev_friday = (end - pd.Timedelta(days=end.weekday() + 3)).normalize()
    prior_idx = s_nav.index[s_nav.index <= prev_friday]
    if len(prior_idx) >= 1:
        res.weekly_return = float(s_nav.iloc[-1] / s_nav.loc[prior_idx[-1]] - 1)
    month_start = end.normalize().replace(day=1)
    quarter_month = ((end.month - 1) // 3) * 3 + 1
    quarter_start = pd.Timestamp(end.year, quarter_month, 1)
    year_start = pd.Timestamp(end.year, 1, 1)
    res.monthly_return = _period_return(s_nav, month_start, end)
    res.quarterly_return = _period_return(s_nav, quarter_start, end)
    res.ytd_return = _period_return(s_nav, year_start, end)

    # ── 8. 年化收益率（按实际交易日数 252 日几何年化）──
    if s_nav.iloc[-1] > 0 and s_nav.iloc[0] > 0 and n_days > 1:
        res.annual_return = float(s_nav.iloc[-1] ** (252.0 / n_days) - 1)

    # ── 9. 年化波动率 ──
    if len(s_ret) >= 5:
        std = float(np.std(s_ret, ddof=1))
        if std > 0:
            res.annual_volatility = float(std * math.sqrt(252))

    # ── 10. Sharpe = (年化收益 - 1.5%) / 年化波动率 ──
    if res.annual_return is not None and res.annual_volatility not in (None, 0, 0.0):
        res.sharpe_ratio = float((res.annual_return - _RISK_FREE_ANNUAL) / res.annual_volatility)

    # ── 11-12. Alpha / Beta（日收益 OLS，Alpha = 日截距 × 252）──
    if b_ret is not None:
        alpha_d, beta = _ols_alpha_beta(s_ret.values, b_ret.values)
        if alpha_d is not None:
            res.alpha = float(alpha_d * 252)
        if beta is not None:
            res.beta = beta

    # ── 13. 跟踪误差 = 日超额 std × √区间交易日数 ──
    # ── 14. 年化跟踪误差 = 日超额 std × √252 ──
    # ── 15. 信息比率 = 日超额均值 / 日超额 std × √252 ──
    if excess_ret is not None and len(excess_ret) >= 5:
        ex_std = float(np.std(excess_ret, ddof=1))
        if ex_std > 0:
            res.tracking_error = float(ex_std * math.sqrt(n_days))
            res.annual_tracking_error = float(ex_std * math.sqrt(252))
            res.information_ratio = float(np.mean(excess_ret) / ex_std * math.sqrt(252))

    # ── 16. 最大回撤 ──
    res.max_drawdown = _max_drawdown(s_nav.values)

    # ── 17-19. 日/周/月胜率 ──
    if len(s_ret) > 0:
        res.daily_win_rate = float((s_ret > 0).sum() / len(s_ret))
    weekly_ret = _resample_returns(s_nav, "W-FRI")
    if len(weekly_ret) > 0:
        res.weekly_win_rate = float((weekly_ret > 0).sum() / len(weekly_ret))
    monthly_ret = _resample_returns(s_nav, "ME")
    if len(monthly_ret) > 0:
        res.monthly_win_rate = float((monthly_ret > 0).sum() / len(monthly_ret))

    # ── 20. Calmar = 年化收益率 / 最大回撤绝对值 ──
    if res.annual_return is not None and res.max_drawdown not in (None, 0, 0.0):
        res.calmar = float(res.annual_return / abs(res.max_drawdown))

    # ── 21-22. 换手率 / 平均持仓天数 ──
    if sub_strategies:
        res.turnover = _compute_turnover(sub_strategies, s_nav.index[-1])
        res.avg_holding_days = _compute_avg_holding_days(sub_strategies, s_nav.index[-1])

    return res


def _compute_turnover(subs: list[SubStrategyTurnover], cutoff: pd.Timestamp) -> Optional[float]:
    """组合换手率 = Σ_sub (build_weight × 0.5 × Σ|Δw|)（公募 build_weight 0 等价不贡献）"""
    total = 0.0
    found_any = False
    for sub in subs:
        if sub.weight_history is None or sub.weight_history.empty:
            continue
        wh = sub.weight_history.loc[sub.weight_history.index <= cutoff].sort_index()
        if len(wh) < 2:
            continue
        # Each row should sum to ~1 (子账户内部权重); take absolute diff between consecutive dates
        diff = wh.diff().abs().fillna(wh.iloc[0])
        # Σ|Δw| for the sub-account over the period
        sum_abs = float(diff.values.sum())
        total += sub.build_weight * 0.5 * sum_abs
        found_any = True
    return float(total) if found_any else None


def _compute_avg_holding_days(subs: list[SubStrategyTurnover], cutoff: pd.Timestamp) -> Optional[Optional[float]]:
    """加权平均持仓天数 = Σ_pos (建仓资金权重 × 该持仓段自然日数) / Σ建仓资金权重

    For each ticker in each sub-strategy's weight_history:
      - find contiguous non-zero segments
      - days = (exit_date or cutoff) - entry_date
      - weight by sub.build_weight × average weight-in-position (we use simple unweighted-by-position
        since the plan says "按建仓资金权重加权" — i.e. weight by sub.build_weight × 1/N positions
        in that sub-account)
    公募不纳入。
    """
    total_weighted_days = 0.0
    total_weight = 0.0
    found_any = False
    for sub in subs:
        if sub.weight_history is None or sub.weight_history.empty:
            continue
        wh = sub.weight_history.loc[sub.weight_history.index <= cutoff].sort_index()
        if len(wh) < 2:
            continue
        tickers = [ticker for ticker in wh.columns if ticker not in sub.cash_columns]
        n_positions = len(tickers)
        if n_positions == 0:
            continue
        # Within this sub-account, weight per position = 1/n_positions
        pos_weight = sub.build_weight / n_positions
        for ticker in tickers:
            col = wh[ticker].fillna(0.0)
            # find contiguous non-zero segments
            in_segment = False
            entry_date = None
            for i in range(len(col)):
                v = col.iloc[i]
                if v > 0 and not in_segment:
                    in_segment = True
                    entry_date = col.index[i]
                elif v <= 0 and in_segment:
                    in_segment = False
                    exit_date = col.index[i]
                    days = (exit_date - entry_date).days
                    if days > 0:
                        total_weighted_days += pos_weight * days
                        total_weight += pos_weight
                    entry_date = None
            # close out still-open position at cutoff
            if in_segment and entry_date is not None:
                days = (cutoff - entry_date).days
                if days > 0:
                    total_weighted_days += pos_weight * days
                    total_weight += pos_weight
        found_any = True
    if not found_any or total_weight == 0:
        return None
    return float(total_weighted_days / total_weight)
