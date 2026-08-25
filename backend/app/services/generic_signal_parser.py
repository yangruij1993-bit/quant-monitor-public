"""
Generic strategy signal parser.

Scans a directory for strategy signal JSON files and parses them into
SignalOverview / SignalDetail objects. No hardcoded strategy logic —
anyone can add a strategy by dropping a JSON file.

Directory structure:
  STRATEGY_DIR/
    my-strategy/
      signal_latest.json          (required)
      signal_history.jsonl        (optional, one JSON per line)
    another-strategy/
      signal_latest.json
"""

import json
import os
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from app.models.signal_schema import (
    SignalOverview, SignalDetail, HoldingsItem,
    BacktestMetrics, SignalHistoryItem,
)
from app.services.pms_metrics import SubStrategyTurnover, compute_pms_metrics

log = logging.getLogger(__name__)

STRATEGY_DIR = os.getenv("STRATEGY_DIR", "./strategies")


def _load_json(path: Path) -> Optional[dict]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning("Failed to load %s: %s", path, e)
        return None


def _parse_overview(data: dict, strategy_id: str) -> SignalOverview:
    holdings = []
    for h in data.get("holdings", []):
        holdings.append(HoldingsItem(
            ticker=str(h.get("ticker", "")),
            name=str(h.get("name", "")),
            weight=float(h.get("weight", 0)),
        ))
    return SignalOverview(
        strategy_id=strategy_id,
        strategy_name=str(data.get("strategy_name", strategy_id)),
        signal_date=str(data.get("signal_date", "")),
        updated_at=str(data.get("updated_at")) if data.get("updated_at") else None,
        holdings=holdings,
        signal_detail=data.get("signal_detail", {}),
    )


_PMS_OPTIONAL_FLOATS = (
    "annual_volatility", "turnover", "absolute_return", "relative_return",
    "relative_return_geometric", "weekly_return", "monthly_return", "quarterly_return",
    "ytd_return", "alpha", "beta", "tracking_error", "annual_tracking_error",
    "information_ratio", "daily_win_rate", "weekly_win_rate", "monthly_win_rate",
    "calmar", "avg_holding_days",
)


def _metrics_from_dict(m: dict) -> BacktestMetrics:
    """Pass through a user-provided metrics block (PMS-aware, None for absent keys)."""
    kwargs = {
        "annual_return": float(m.get("annual_return", 0)),
        "max_drawdown": float(m.get("max_drawdown", 0)),
        "sharpe_ratio": float(m.get("sharpe_ratio", 0)),
        "win_rate": float(m.get("win_rate", 0)),
        "period_start": str(m.get("period_start", "")),
        "period_end": str(m.get("period_end", "")),
    }
    for key in _PMS_OPTIONAL_FLOATS:
        if key in m and m[key] is not None:
            kwargs[key] = float(m[key])
    return BacktestMetrics(**kwargs)


def _nav_series(nav_data: dict) -> Optional[pd.Series]:
    dates = nav_data.get("dates")
    values = nav_data.get("values")
    if not dates or not values or len(dates) != len(values):
        return None
    s = pd.Series(
        pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(),
        index=pd.to_datetime(pd.Series(dates), errors="coerce"),
        dtype=float,
    )
    s = s[s.index.notna()]
    s = s[(s > 0) & s.notna()].sort_index()
    return s[~s.index.duplicated(keep="last")]


def _benchmark_series(nav_data: dict) -> Optional[pd.Series]:
    bench = nav_data.get("benchmark_nav")
    if not bench:
        return None
    return _nav_series({"dates": nav_data["dates"], "values": bench})


def _weight_history_from_rows(rows: list[dict]) -> Optional[pd.DataFrame]:
    """Rebuild a weight history from optional holdings snapshots in history rows."""
    snaps: list[tuple[pd.Timestamp, dict[str, float]]] = []
    for row in rows:
        holdings = row.get("holdings")
        if not holdings:
            continue
        d = pd.to_datetime(str(row.get("date", "")), errors="coerce")
        if pd.isna(d):
            continue
        snaps.append((d, {
            str(h.get("ticker", "")): float(h.get("weight", 0) or 0) for h in holdings
        }))
    if len(snaps) < 2:
        return None
    snaps.sort(key=lambda x: x[0])
    tickers = sorted({t for _, h in snaps for t in h})
    wh = pd.DataFrame(0.0, index=pd.DatetimeIndex([d for d, _ in snaps]), columns=tickers)
    for d, h in snaps:
        for t, w in h.items():
            wh.loc[d, t] = w
    return wh


def compute_backtest_metrics(nav_data: dict, history_rows: list[dict] | None = None) -> Optional[BacktestMetrics]:
    """Compute the 22 PMS metrics from a nav block (benchmark optional)."""
    s = _nav_series(nav_data or {})
    if s is None or len(s) < 2:
        return None
    b = _benchmark_series(nav_data or {})
    s = s / s.iloc[0]
    if b is not None:
        common = s.index.intersection(b.index)
        if len(common) >= 2:
            b = b[common] / b[common].iloc[0]
            s = s[common]
        else:
            b = None
    sub_strategies = None
    wh = _weight_history_from_rows(history_rows or [])
    if wh is not None:
        sub_strategies = [SubStrategyTurnover(
            name="strategy", build_weight=1.0, weight_history=wh, cash_columns=frozenset(),
        )]
    res = compute_pms_metrics(s, b, sub_strategies=sub_strategies)
    if res.annual_return is None and res.max_drawdown is None:
        return None
    return BacktestMetrics(**res.to_metrics_dict())


def _excess_from_nav(nav_values: list[float], bench_values: list[float]) -> list[float]:
    s0, b0 = nav_values[0], bench_values[0]
    return [round((s / s0) / (bv / b0) - 1.0, 8) for s, bv in zip(nav_values, bench_values)]


def _parse_detail(data: dict, strategy_id: str, history_rows: list[dict] | None = None) -> SignalDetail:
    history_rows = history_rows or []
    overview = _parse_overview(data, strategy_id)
    detail = SignalDetail(
        strategy_id=overview.strategy_id,
        strategy_name=overview.strategy_name,
        signal_date=overview.signal_date,
        holdings=overview.holdings,
        signal_detail=overview.signal_detail,
        updated_at=overview.updated_at,
    )
    # Optional NAV
    nav_data = data.get("nav")
    if nav_data and "values" in nav_data and len(nav_data["values"]) > 0:
        detail.nav_latest = float(nav_data["values"][-1])
    # Optional metrics — user-provided takes priority; otherwise auto-compute from nav.
    m = data.get("metrics")
    if m:
        detail.metrics = _metrics_from_dict(m)
    else:
        detail.metrics = compute_backtest_metrics(data.get("nav") or {}, history_rows)
    return detail


class GenericSignalParser:
    """Directory-scanning generic signal parser."""

    def discover_strategies(self) -> list[str]:
        """List all strategy IDs found in STRATEGY_DIR."""
        base = Path(STRATEGY_DIR)
        if not base.is_dir():
            return []
        ids = []
        for d in sorted(base.iterdir()):
            if d.is_dir() and (d / "signal_latest.json").exists():
                ids.append(d.name)
        return ids

    def get_overview(self, strategy_id: str) -> Optional[SignalOverview]:
        path = Path(STRATEGY_DIR) / strategy_id / "signal_latest.json"
        if not path.exists():
            return None
        data = _load_json(path)
        if not data:
            return None
        return _parse_overview(data, strategy_id)

    def get_overviews(self) -> list[SignalOverview]:
        results = []
        for sid in self.discover_strategies():
            try:
                ov = self.get_overview(sid)
                if ov:
                    results.append(ov)
            except Exception as e:
                log.warning("Error parsing strategy %s: %s", sid, e)
        return results

    def get_raw(self, strategy_id: str) -> Optional[dict]:
        path = Path(STRATEGY_DIR) / strategy_id / "signal_latest.json"
        if not path.exists():
            return None
        return _load_json(path)

    def get_raw_history(self, strategy_id: str) -> list[dict]:
        path = Path(STRATEGY_DIR) / strategy_id / "signal_history.jsonl"
        if not path.exists():
            return []
        rows = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
        except Exception:
            return []
        return rows

    def get_detail(self, strategy_id: str) -> Optional[SignalDetail]:
        path = Path(STRATEGY_DIR) / strategy_id / "signal_latest.json"
        if not path.exists():
            return None
        data = _load_json(path)
        if not data:
            return None
        return _parse_detail(data, strategy_id, history_rows=self.get_raw_history(strategy_id))

    def get_nav(self, strategy_id: str):
        """Return nav curves from signal JSON (benchmark passthrough + excess auto-derive)."""
        from app.models.signal_schema import NavCurve
        path = Path(STRATEGY_DIR) / strategy_id / "signal_latest.json"
        if not path.exists():
            return None
        data = _load_json(path)
        nav_data = (data or {}).get("nav")
        if not nav_data or "dates" not in nav_data or "values" not in nav_data:
            return None
        bench = nav_data.get("benchmark_nav")
        excess = nav_data.get("excess_nav")
        excess_name = nav_data.get("excess_name")
        if bench and len(bench) == len(nav_data["values"]):
            if excess is None:
                excess = _excess_from_nav(
                    [float(v) for v in nav_data["values"]], [float(v) for v in bench]
                )
                excess_name = excess_name or "累计超额收益 (策略/基准 - 1)"
        else:
            bench = None
        return NavCurve(
            strategy_id=strategy_id,
            dates=nav_data["dates"],
            nav=nav_data["values"],
            benchmark_nav=bench,
            benchmark_name=nav_data.get("benchmark_name") if bench else None,
            excess_nav=excess,
            excess_name=excess_name,
        )

    def get_history(self, strategy_id: str, limit: int = 30) -> list[SignalHistoryItem]:
        """Read signal_history.jsonl if present."""
        path = Path(STRATEGY_DIR) / strategy_id / "signal_history.jsonl"
        if not path.exists():
            return []
        items = []
        try:
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            return []
        for line in reversed(lines[-limit:]):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                detail = dict(entry.get("detail") or {})
                if entry.get("holdings"):
                    detail["holdings"] = entry["holdings"]
                items.append(SignalHistoryItem(
                    date=str(entry.get("date", "")),
                    action=str(entry.get("action", "")),
                    detail=detail,
                ))
            except Exception:
                continue
        return items[:limit]


generic_signal_parser = GenericSignalParser()
