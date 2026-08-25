"""_demo 数据契约：长度对齐、无 metrics 键、history 含 holdings 快照。"""
import json
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parents[2] / "strategies" / "_demo"


def _latest() -> dict:
    return json.loads((DEMO_DIR / "signal_latest.json").read_text(encoding="utf-8"))


def test_demo_nav_lengths_aligned():
    nav = _latest()["nav"]
    assert len(nav["dates"]) == len(nav["values"]) == len(nav["benchmark_nav"])
    assert len(nav["dates"]) >= 60
    assert nav["benchmark_name"]


def test_demo_has_no_handwritten_metrics():
    assert "metrics" not in _latest()


def test_demo_history_has_holdings_snapshots():
    lines = [
        json.loads(l)
        for l in (DEMO_DIR / "signal_history.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    with_holdings = [l for l in lines if "holdings" in l]
    assert len(with_holdings) >= 2
    for row in with_holdings:
        assert row["holdings"]
        total = sum(h["weight"] for h in row["holdings"])
        assert abs(total - 1.0) < 1e-9
