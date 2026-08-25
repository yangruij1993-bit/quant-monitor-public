"""
Tests for the PMS 22-metric calculator (generic, benchmark optional).
- Hand-computable samples for core formulas
- Zero-variance / too-short samples return None (not 0)
- Benchmark-optional degraded mode
- Turnover / avg-holding-days from weight history
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.pms_metrics import (  # noqa: E402
    compute_pms_metrics,
    SubStrategyTurnover,
)


# ── Item 5: Hand-computable sample for 22 formulas ───────────────────


def test_hand_computable_sample_core_metrics():
    """
    10-day sample with known values. Verify:
    - absolute_return = nav[-1] - 1
    - relative_return = strategy_total - bench_total
    - relative_return_geometric = nav[-1] / bench[-1] - 1
    - max_drawdown = (trough - peak) / peak
    - daily_win_rate = #(strategy_ret > 0) / N
    - calmar = annual_return / |max_dd|
    - alpha = OLS intercept * 252
    - beta = OLS slope
    """
    # Strategy: 1.0, 1.02, 1.01, 1.04, 1.03, 1.06, 1.05, 1.08, 1.07, 1.10
    # Bench:    1.0, 1.01, 1.00, 1.02, 1.01, 1.03, 1.02, 1.04, 1.03, 1.05
    s_values = [1.0, 1.02, 1.01, 1.04, 1.03, 1.06, 1.05, 1.08, 1.07, 1.10]
    b_values = [1.0, 1.01, 1.00, 1.02, 1.01, 1.03, 1.02, 1.04, 1.03, 1.05]
    dates = pd.date_range("2026-01-05", periods=10, freq="B")
    s_nav = pd.Series(s_values, index=dates)
    b_nav = pd.Series(b_values, index=dates)

    res = compute_pms_metrics(s_nav, b_nav)
    d = res.to_metrics_dict()

    # Absolute return
    assert d["annual_return"] is not None
    assert abs(res.absolute_return - 0.10) < 1e-9

    # Relative return (arithmetic)
    s_total = s_values[-1] / s_values[0] - 1  # 0.10
    b_total = b_values[-1] / b_values[0] - 1  # 0.05
    assert abs(res.relative_return - (s_total - b_total)) < 1e-9

    # Geometric relative
    expected_geo = s_values[-1] / b_values[-1] - 1
    assert abs(res.relative_return_geometric - expected_geo) < 1e-9

    # Max drawdown: peak=1.08 at idx 7, trough=1.07 at idx 8 → -1/108 ≈ -0.00926
    # But also need to check intermediate: peak so far vs current
    # idx 1: 1.02, idx 2: 1.01 (dd = 1.01/1.02 - 1 = -0.00980)
    # idx 4: 1.03 vs 1.04 → -0.00961
    # idx 6: 1.05 vs 1.06 → -0.00943
    # idx 8: 1.07 vs 1.08 → -0.00926
    # min ≈ -0.00980
    assert res.max_drawdown is not None
    assert abs(res.max_drawdown - (-0.009803921)) < 1e-6

    # Daily win rate: positive-return days
    s_ret = np.diff(s_values) / np.array(s_values[:-1])
    expected_win = float((s_ret > 0).sum() / len(s_ret))
    assert abs(res.daily_win_rate - expected_win) < 1e-9

    # Beta from OLS
    b_ret = np.diff(b_values) / np.array(b_values[:-1])
    x = b_ret - b_ret.mean()
    y = s_ret - s_ret.mean()
    expected_beta = float((x * y).sum() / (x * x).sum())
    assert abs(res.beta - expected_beta) < 1e-9

    # Alpha = OLS intercept * 252
    expected_alpha = float(s_ret.mean() - expected_beta * b_ret.mean()) * 252
    assert abs(res.alpha - expected_alpha) < 1e-6


def test_period_returns_week_month_quarter_year():
    """
    Verify weekly/monthly/quarterly/ytd return.
    Weekly = 上周五收盘 → end (end 所在周之前的最近上周五).
    Monthly/Quarterly/YTD picks first common trade day >= period start.
    """
    # Build a series with dates spanning multiple periods
    dates = pd.to_datetime([
        "2025-12-31", "2026-01-02", "2026-01-15",
        "2026-04-01", "2026-04-15",
        "2026-06-29", "2026-06-30", "2026-07-01", "2026-07-02",
    ])
    s_values = [1.0, 1.01, 1.02, 1.05, 1.06, 1.10, 1.08, 1.09, 1.12]
    b_values = [1.0, 1.005, 1.01, 1.02, 1.025, 1.04, 1.03, 1.035, 1.04]
    s_nav = pd.Series(s_values, index=dates)
    b_nav = pd.Series(b_values, index=dates)

    res = compute_pms_metrics(s_nav, b_nav)

    # End = 2026-07-02 (last, Thursday)
    # YTD start = 2026-01-01 → first date >= is 2026-01-02 (s=1.01)
    # ytd_return = 1.12 / 1.01 - 1
    expected_ytd = 1.12 / 1.01 - 1
    assert abs(res.ytd_return - expected_ytd) < 1e-6

    # Quarter Q3 starts 2026-07-01 → first date >= is 2026-07-01 (s=1.09)
    # quarterly_return = 1.12 / 1.09 - 1
    expected_q = 1.12 / 1.09 - 1
    assert abs(res.quarterly_return - expected_q) < 1e-6

    # Month July starts 2026-07-01 → s=1.09
    expected_m = 1.12 / 1.09 - 1
    assert abs(res.monthly_return - expected_m) < 1e-6

    # Week: end=2026-07-02 (Thursday, weekday=3) → prev_friday = 7/2 - 6d = 2026-06-26.
    # 6/26 不在数据里, 取 <= prev_friday 的最后一个交易日 = 2026-04-15 (s=1.06).
    # weekly_return = 1.12 / 1.06 - 1
    expected_w = 1.12 / 1.06 - 1
    assert abs(res.weekly_return - expected_w) < 1e-6


def test_weekly_return_prev_friday_to_end():
    """Weekly = 上周五收盘 → end. 连续交易周场景: end=周五时应等于过去 5 个交易日累计收益."""
    # 模拟 7/3 (上周五) ~ 7/10 (本周五) 完整两周
    dates = pd.to_datetime([
        "2026-07-03",
        "2026-07-06", "2026-07-07", "2026-07-08", "2026-07-09", "2026-07-10",
    ])
    s_values = [1.06, 1.048917, 1.038750, 1.018119, 1.058233, 1.023180]
    b_values = [1.0, 0.985, 0.97, 0.955, 0.985, 0.97]
    s_nav = pd.Series(s_values, index=dates)
    b_nav = pd.Series(b_values, index=dates)

    res = compute_pms_metrics(s_nav, b_nav)

    # end=7/10 (Friday, weekday=4) → prev_friday = 7/10 - 7d = 7/3, 在数据里
    # weekly_return = s_nav[7/10] / s_nav[7/3] - 1
    expected_w = 1.023180 / 1.06 - 1
    assert abs(res.weekly_return - expected_w) < 1e-6
    # 关键: 不是 ISO 周一→周五 的 -2.45%, 而是包含周一跳空后的 -3.9%


def test_sharpe_formula():
    """Sharpe = (annual_return - 1.5%) / annual_volatility."""
    np.random.seed(0)
    n = 252
    dates = pd.date_range("2026-01-01", periods=n, freq="B")
    s_nav = pd.Series(np.cumprod(1 + np.random.normal(0.001, 0.01, n)), index=dates)
    b_nav = pd.Series(np.cumprod(1 + np.random.normal(0.0005, 0.008, n)), index=dates)
    res = compute_pms_metrics(s_nav, b_nav)

    assert res.annual_return is not None
    assert res.annual_volatility is not None
    expected_sharpe = (res.annual_return - 0.015) / res.annual_volatility
    assert abs(res.sharpe_ratio - expected_sharpe) < 1e-9


def test_information_ratio_and_tracking_error():
    """IR = mean(excess) / std(excess) × √252; annual TE = std(excess) × √252."""
    np.random.seed(42)
    n = 100
    dates = pd.date_range("2026-01-01", periods=n, freq="B")
    s_nav = pd.Series(np.cumprod(1 + np.random.normal(0.002, 0.012, n)), index=dates)
    b_nav = pd.Series(np.cumprod(1 + np.random.normal(0.0005, 0.008, n)), index=dates)
    res = compute_pms_metrics(s_nav, b_nav)

    s_ret = s_nav.pct_change().dropna()
    b_ret = b_nav.pct_change().dropna()
    excess = (s_ret - b_ret).dropna()
    expected_te = float(np.std(excess, ddof=1) * np.sqrt(252))
    expected_ir = float(np.mean(excess) / np.std(excess, ddof=1) * np.sqrt(252))

    assert abs(res.annual_tracking_error - expected_te) < 1e-9
    assert abs(res.information_ratio - expected_ir) < 1e-9


def test_calmar_ratio():
    """Calmar = annual_return / |max_dd|."""
    s_values = [1.0, 1.10, 1.05, 1.15, 1.20]
    b_values = [1.0, 1.02, 1.01, 1.03, 1.04]
    dates = pd.date_range("2026-01-05", periods=5, freq="B")
    s_nav = pd.Series(s_values, index=dates)
    b_nav = pd.Series(b_values, index=dates)
    res = compute_pms_metrics(s_nav, b_nav)

    assert res.annual_return is not None
    assert res.max_drawdown is not None
    expected_calmar = res.annual_return / abs(res.max_drawdown)
    assert abs(res.calmar - expected_calmar) < 1e-9


# ── Item 6: Zero variance / short sample returns None ────────────────


def test_zero_variance_returns_none_for_volatility_sharpe():
    """Flat strategy NAV → annual_volatility / sharpe / alpha / beta all None."""
    s_values = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    b_values = [1.0, 1.01, 1.00, 1.02, 1.01, 1.03, 1.02, 1.04, 1.03, 1.05]
    dates = pd.date_range("2026-01-05", periods=10, freq="B")
    s_nav = pd.Series(s_values, index=dates)
    b_nav = pd.Series(b_values, index=dates)
    res = compute_pms_metrics(s_nav, b_nav)

    assert res.annual_volatility is None
    assert res.sharpe_ratio is None
    assert res.alpha is None
    assert res.beta is None
    assert res.calmar is None  # depends on max_dd != 0, here max_dd=0 so None


def test_short_sample_returns_none_metrics():
    """Only 1 common day → almost everything None."""
    dates = pd.date_range("2026-01-05", periods=1, freq="B")
    s_nav = pd.Series([1.0], index=dates)
    b_nav = pd.Series([1.0], index=dates)
    res = compute_pms_metrics(s_nav, b_nav)
    assert res.absolute_return is None
    assert res.annual_return is None
    assert res.sharpe_ratio is None


# ── Item 1: Fixed-share buyhold ≠ daily-equal-weight ────────────────


def test_fixed_share_buyhold_differs_from_daily_equal_weight():
    """Two funds with different price paths. Fixed-share ≠ equal-weight rebalanced."""
    # Fund A: 1.0 → 1.5 → 1.5 (steady up)
    # Fund B: 1.0 → 1.0 → 2.0 (catch-up)
    # Equal capital at build → shares_A = shares_B = 0.5 / 1.0 = 0.5
    # Fixed-share NAV[t=2] = (0.5*1.5 + 0.5*2.0) / (0.5*1.0 + 0.5*1.0) = 1.75
    # Daily equal weight: t=1 rets: A=+50%, B=0%, avg=+25% → nav=1.25
    # t=2 rets: A=0%, B=+100%, avg=+50% → nav=1.25*1.5=1.875
    fund_a = pd.Series([1.0, 1.5, 1.5], index=pd.date_range("2026-01-05", periods=3, freq="B"))
    fund_b = pd.Series([1.0, 1.0, 2.0], index=pd.date_range("2026-01-05", periods=3, freq="B"))

    # Fixed-share
    build = pd.Timestamp("2026-01-05")
    shares_a = 0.5 / fund_a.loc[build]
    shares_b = 0.5 / fund_b.loc[build]
    fixed_nav = (shares_a * fund_a + shares_b * fund_b)
    fixed_nav = fixed_nav / fixed_nav.iloc[0]

    # Daily equal weight
    rets_a = fund_a.pct_change().fillna(0)
    rets_b = fund_b.pct_change().fillna(0)
    avg_ret = (rets_a + rets_b) / 2
    daily_eq_nav = (1 + avg_ret).cumprod()
    daily_eq_nav.iloc[0] = 1.0

    # Final values clearly differ
    assert abs(fixed_nav.iloc[-1] - 1.75) < 1e-9
    assert abs(daily_eq_nav.iloc[-1] - 1.875) < 1e-9
    assert fixed_nav.iloc[-1] != daily_eq_nav.iloc[-1]


# ── Item 21: Turnover / 22: avg_holding_days ─────────────────────────


def test_turnover_computation():
    """Sub-account turnover = 0.5 × Σ|Δw|, weighted by build weight."""
    # Sub-account: 1 ticker, weight goes 0.0 → 1.0 → 0.0 → 1.0 over 4 days
    wh = pd.DataFrame(
        {"A": [0.0, 1.0, 0.0, 1.0]},
        index=pd.date_range("2026-01-05", periods=4, freq="B"),
    )
    sub = SubStrategyTurnover(name="test", build_weight=0.5, weight_history=wh)
    # diff.abs().sum() = 1.0 + 1.0 + 1.0 = 3.0; turnover = 0.5 * 0.5 * 3.0 = 0.75
    s_nav = pd.Series([1.0, 1.0, 1.0, 1.0], index=wh.index)
    b_nav = pd.Series([1.0, 1.0, 1.0, 1.0], index=wh.index)
    res = compute_pms_metrics(s_nav, b_nav, sub_strategies=[sub])
    # turnover for the period
    assert res.turnover is not None
    assert abs(res.turnover - 0.75) < 1e-9


def test_avg_holding_days_basic():
    """Single position held 10 calendar days → avg = 10."""
    dates = pd.date_range("2026-01-05", periods=3, freq="B")  # 1/5, 1/6, 1/7
    wh = pd.DataFrame(
        {"A": [1.0, 1.0, 0.0]},
        index=dates,
    )
    sub = SubStrategyTurnover(name="test", build_weight=1.0, weight_history=wh)
    s_nav = pd.Series([1.0, 1.0, 1.0], index=dates)
    b_nav = pd.Series([1.0, 1.0, 1.0], index=dates)
    res = compute_pms_metrics(s_nav, b_nav, sub_strategies=[sub])
    # Position entered at 1/5, exited at 1/7 → 2 calendar days
    assert res.avg_holding_days is not None
    assert abs(res.avg_holding_days - 2.0) < 1e-9


def test_turnover_includes_cash_but_holding_days_exclude_cash():
    dates = pd.to_datetime(["2026-05-01", "2026-05-02", "2026-05-05"])
    wh = pd.DataFrame(
        {"AAA": [0.0, 0.5, 0.0], "CASH": [1.0, 0.5, 1.0]},
        index=dates,
    )
    sub = SubStrategyTurnover(
        name="cash-aware",
        build_weight=1.0,
        weight_history=wh,
        cash_columns=frozenset({"CASH"}),
    )
    nav = pd.Series([1.0, 1.01, 1.0], index=dates)
    benchmark = pd.Series([1.0, 1.0, 1.0], index=dates)

    result = compute_pms_metrics(nav, benchmark, sub_strategies=[sub])

    assert result.turnover == pytest.approx(1.5)
    assert result.avg_holding_days == pytest.approx(3.0)


def test_no_benchmark_returns_absolute_metrics_only():
    idx = pd.date_range("2026-01-05", periods=40, freq="B")
    rng = np.random.default_rng(7)
    s = pd.Series((1.0 + rng.normal(0.0005, 0.01, 40)).cumprod(), index=idx)
    res = compute_pms_metrics(s, None)
    assert res.absolute_return is not None
    assert res.annual_return is not None
    assert res.max_drawdown is not None
    assert res.sharpe_ratio is not None
    assert res.relative_return is None
    assert res.relative_return_geometric is None
    assert res.alpha is None
    assert res.beta is None
    assert res.tracking_error is None
    assert res.annual_tracking_error is None
    assert res.information_ratio is None
    d = res.to_metrics_dict()
    assert d["alpha"] is None
    assert d["beta"] is None
