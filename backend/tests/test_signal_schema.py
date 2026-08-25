from app.models.signal_schema import BacktestMetrics, NavCurve


def test_backtest_metrics_backward_compatible_with_old_fields_only():
    m = BacktestMetrics(
        annual_return=0.1, max_drawdown=-0.05, sharpe_ratio=1.2, win_rate=0.55,
        period_start="2026-01-01", period_end="2026-06-30",
    )
    assert m.alpha is None and m.turnover is None


def test_backtest_metrics_accepts_all_22_fields():
    m = BacktestMetrics(
        annual_return=0.1, max_drawdown=-0.05, sharpe_ratio=1.2, win_rate=0.55,
        period_start="2026-01-01", period_end="2026-06-30",
        absolute_return=0.2, relative_return=0.05, relative_return_geometric=0.04,
        weekly_return=0.01, monthly_return=0.02, quarterly_return=0.03, ytd_return=0.08,
        alpha=0.02, beta=0.9, tracking_error=0.01, annual_tracking_error=0.05,
        information_ratio=1.1, daily_win_rate=0.52, weekly_win_rate=0.55,
        monthly_win_rate=0.6, calmar=2.0, turnover=3.2, avg_holding_days=45.0,
    )
    assert m.information_ratio == 1.1


def test_nav_curve_excess_fields_optional():
    c = NavCurve(strategy_id="x", dates=["2026-01-02"], nav=[1.0])
    assert c.benchmark_nav is None and c.excess_nav is None and c.excess_name is None
