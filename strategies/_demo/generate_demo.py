#!/usr/bin/env python3
"""Generate deterministic demo strategy data (nav + benchmark + holdings history).

This is a reference example of the strategy JSON contract:
  - signal_latest.json: nav block with dates/values + benchmark_nav/benchmark_name
  - signal_history.jsonl: action log with optional holdings snapshots
Metrics are intentionally omitted so the backend auto-computes them.

Rerun:  python3 strategies/_demo/generate_demo.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
END_DATE = "2026-06-12"
N_DAYS = 120


def build_nav() -> tuple[list[str], list[float], list[float]]:
    dates = pd.bdate_range(end=END_DATE, periods=N_DAYS)
    rng = np.random.default_rng(42)
    s_ret = 0.0006 + rng.normal(0.0, 0.009, N_DAYS)
    b_ret = 0.0004 + rng.normal(0.0, 0.007, N_DAYS)
    s_ret[40:55] -= 0.006  # 一段约 -8% 的回撤
    nav = (1.0 + s_ret).cumprod()
    bench = (1.0 + b_ret).cumprod()
    return (
        [d.strftime("%Y-%m-%d") for d in dates],
        [round(float(v), 6) for v in nav],
        [round(float(v), 6) for v in bench],
    )


HOLDINGS_SCHEDULE = [
    (0, "建仓", [("510300.SH", "沪深300 ETF", 0.6), ("511010.SH", "国债 ETF", 0.4)]),
    (30, "调仓", [("510300.SH", "沪深300 ETF", 0.4), ("511010.SH", "国债 ETF", 0.6)]),
    (75, "调仓", [("510300.SH", "沪深300 ETF", 0.5), ("511010.SH", "国债 ETF", 0.5)]),
]


def main() -> None:
    dates, nav, bench = build_nav()
    latest = {
        "_demo": True,
        "_comment": "示例策略（脚本 generate_demo.py 生成，确定性随机种子）。metrics 字段故意缺省，由后端自动计算。不构成任何投资建议。",
        "strategy_id": "_demo",
        "strategy_name": "【示例·Demo】60/40 股债定投（请删除）",
        "signal_date": dates[-1],
        "holdings": [
            {"ticker": "510300.SH", "name": "沪深300 ETF", "weight": 0.5},
            {"ticker": "511010.SH", "name": "国债 ETF", "weight": 0.5},
        ],
        "signal_detail": {
            "信号": "持有（示例）",
            "再平衡频率": "季度",
            "is_demo": True,
        },
        "nav": {
            "dates": dates,
            "values": nav,
            "benchmark_nav": bench,
            "benchmark_name": "沪深300 ETF",
        },
    }
    (HERE / "signal_latest.json").write_text(
        json.dumps(latest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = []
    for idx, action, holdings in HOLDINGS_SCHEDULE:
        row = {
            "date": dates[idx],
            "action": action,
            "detail": {"reason": f"demo {action}"},
            "holdings": [
                {"ticker": t, "name": n, "weight": w} for t, n, w in holdings
            ],
        }
        lines.append(json.dumps(row, ensure_ascii=False))
    for idx in (10, 50, 90, 110):
        lines.append(json.dumps(
            {"date": dates[idx], "action": "持有", "detail": {"reason": "demo hold"}},
            ensure_ascii=False,
        ))
    lines.sort(key=lambda s: json.loads(s)["date"])
    (HERE / "signal_history.jsonl").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(f"wrote {HERE/'signal_latest.json'} and signal_history.jsonl ({len(dates)} nav points)")


if __name__ == "__main__":
    main()
