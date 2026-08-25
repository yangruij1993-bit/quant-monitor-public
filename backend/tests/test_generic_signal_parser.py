"""Parser auto-compute: metrics passthrough priority, nav-driven computation,
benchmark excess derivation, holdings-history turnover."""
import importlib
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DEMO_DIR = Path(__file__).resolve().parents[2] / "strategies" / "_demo"


@pytest.fixture()
def parser_with_demo(monkeypatch):
    monkeypatch.setenv("STRATEGY_DIR", str(DEMO_DIR.parent))
    import app.services.generic_signal_parser as gsp
    return importlib.reload(gsp).generic_signal_parser


def test_get_nav_returns_benchmark_and_computes_excess(parser_with_demo):
    nav = parser_with_demo.get_nav("_demo")
    assert nav is not None
    assert nav.benchmark_nav is not None
    assert nav.benchmark_name == "沪深300 ETF"
    assert nav.excess_nav is not None
    assert len(nav.excess_nav) == len(nav.nav)
    assert abs(nav.excess_nav[0]) < 1e-12  # 起点归一


def test_get_detail_autocomputes_metrics(parser_with_demo):
    detail = parser_with_demo.get_detail("_demo")
    assert detail is not None
    m = detail.metrics
    assert m is not None  # JSON 无 metrics 字段 → 自动计算
    assert m.annual_return is not None
    assert m.max_drawdown is not None
    assert m.alpha is not None  # 有基准 → 相对指标可用
    assert m.turnover is not None  # history 有 ≥2 个 holdings 快照
    assert m.avg_holding_days is not None


def test_metrics_passthrough_takes_priority(parser_with_demo, tmp_path):
    src = json.loads((DEMO_DIR / "signal_latest.json").read_text(encoding="utf-8"))
    src["metrics"] = {
        "annual_return": 0.99, "max_drawdown": -0.01, "sharpe_ratio": 9.9,
        "win_rate": 0.9, "period_start": "2026-01-01", "period_end": "2026-01-02",
    }
    strat = tmp_path / "passthrough"
    strat.mkdir()
    (strat / "signal_latest.json").write_text(json.dumps(src), encoding="utf-8")
    import app.services.generic_signal_parser as gsp
    gsp.STRATEGY_DIR = str(tmp_path)
    try:
        m = gsp.generic_signal_parser.get_detail("passthrough").metrics
        assert m is not None
        assert m.annual_return == 0.99  # 用户自带 metrics 优先
    finally:
        gsp.STRATEGY_DIR = os.getenv("STRATEGY_DIR", "./strategies")


def test_degraded_mode_without_benchmark(parser_with_demo, tmp_path):
    src = json.loads((DEMO_DIR / "signal_latest.json").read_text(encoding="utf-8"))
    src["nav"].pop("benchmark_nav")
    src["nav"].pop("benchmark_name")
    strat = tmp_path / "nobench"
    strat.mkdir()
    (strat / "signal_latest.json").write_text(json.dumps(src), encoding="utf-8")
    import app.services.generic_signal_parser as gsp
    gsp.STRATEGY_DIR = str(tmp_path)
    try:
        detail = gsp.generic_signal_parser.get_detail("nobench")
        assert detail.metrics is not None
        assert detail.metrics.alpha is None  # 无基准 → 相对指标为 None
        assert detail.metrics.annual_return is not None
        nav = gsp.generic_signal_parser.get_nav("nobench")
        assert nav.excess_nav is None
    finally:
        gsp.STRATEGY_DIR = os.getenv("STRATEGY_DIR", "./strategies")
