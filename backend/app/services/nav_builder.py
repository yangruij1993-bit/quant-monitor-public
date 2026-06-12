"""
NAV curve builder for all strategies.
Three reconstruction methods:
1. Direct read (sharpe-rotation) — read nav.csv
2. Trade-level cumulation (weekend-arb) — cumulate net_return
3. Weight-based reconstruction (macro-6cycle, cn-us-hk-timing, us-fusion, csi500-timing)
"""

import os
import glob
import asyncio
import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.models.signal_schema import NavCurve, BacktestMetrics

_BASE = os.getenv(
    "STRATEGY_DATA_DIR",
    "/Users/xinghuazhang/ygr-project/行业轮动/quant_code_product/实盘代码-20260520/实盘代码",
)


class NavBuilder:

    def get_nav(self, strategy_id: str) -> NavCurve | None:
        handler = {
            "sharpe-rotation": self._nav_sharpe_rotation,
            "weekend-arb": self._nav_weekend_arb,
            "macro-6cycle": self._nav_macro_6cycle,
            "cn-us-hk-timing": self._nav_cn_us_hk_timing,
            "us-fusion": self._nav_us_fusion,
            "csi500-timing": self._nav_csi500_timing,
            "spmo-usmv-64": self._nav_spmo_usmv_64,
        }.get(strategy_id)
        if not handler:
            return None
        return handler()

    def compute_metrics(self, strategy_id: str) -> BacktestMetrics | None:
        curve = self.get_nav(strategy_id)
        if not curve or len(curve.nav) < 10:
            return None
        nav = np.array(curve.nav)
        returns = np.diff(nav) / nav[:-1]

        # Use actual calendar span for annualization (works for daily or irregular data)
        from datetime import datetime as _dt
        start = _dt.strptime(curve.dates[0][:10], "%Y-%m-%d")
        end = _dt.strptime(curve.dates[-1][:10], "%Y-%m-%d")
        years = (end - start).days / 365.25
        if years <= 0:
            return None

        total_return = nav[-1] / nav[0] - 1
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

        # Max drawdown
        peak = np.maximum.accumulate(nav)
        drawdown = (nav - peak) / peak
        max_drawdown = float(np.min(drawdown))

        # Periods per year (from actual data frequency)
        periods_per_year = len(returns) / years if years > 0 else 252

        # Sharpe ratio (assume risk-free = 0)
        mean_ret = np.mean(returns)
        std_ret = np.std(returns)
        sharpe = float(mean_ret / std_ret * np.sqrt(periods_per_year)) if std_ret > 0 else 0

        # Win rate (positive period returns)
        win_rate = float(np.sum(returns > 0) / len(returns))

        # Annual volatility
        annual_vol = float(std_ret * np.sqrt(periods_per_year))

        return BacktestMetrics(
            annual_return=round(annual_return, 4),
            max_drawdown=round(max_drawdown, 4),
            sharpe_ratio=round(sharpe, 2),
            win_rate=round(win_rate, 4),
            annual_volatility=round(annual_vol, 4),
            period_start=curve.dates[0],
            period_end=curve.dates[-1],
        )

    # ── sharpe-rotation: direct read from nav.csv ────────────

    def _nav_sharpe_rotation(self) -> NavCurve | None:
        path = os.path.join(
            _BASE, "output/sharpe_ma252_divlv_gv_5050/nav.csv"
        )
        if not os.path.exists(path):
            return None
        df = pd.read_csv(path, encoding="utf-8-sig")
        if df.empty:
            return None
        return NavCurve(
            strategy_id="sharpe-rotation",
            dates=df["trade_date"].tolist(),
            nav=df["nav_final"].tolist(),
        )

    # ── weekend-arb: cumulate net_return per signal ──────────

    def _nav_weekend_arb(self) -> NavCurve | None:
        path = os.getenv(
            "WEEKEND_ARB_DIR",
            "/Users/xinghuazhang/ygr-project/行业轮动/股指周末套利策略代码",
        )
        csv_file = os.path.join(path, "all_signals_ic_weekend_speculation.csv")
        if not os.path.exists(csv_file):
            return None
        df = pd.read_csv(csv_file, encoding="utf-8-sig")
        if df.empty:
            return None

        # Filter to completed trades only
        if "trade_status" in df.columns:
            df = df[df["trade_status"].astype(str).str.strip() == "completed"]
        if df.empty:
            return None

        # Use per-index cumulative NAV
        # Group by signal_date, average net_return across indices for equal-weight portfolio
        df["signal_date"] = pd.to_datetime(df["signal_date"])
        daily_returns = df.groupby("signal_date")["net_return"].mean()
        daily_returns = daily_returns.sort_index()

        nav = 1.0
        navs = [1.0]
        dates = [str(daily_returns.index[0].date())]
        for dt, ret in daily_returns.iloc[1:].items():
            nav *= (1 + ret)
            navs.append(round(nav, 6))
            dates.append(str(dt.date()))

        return NavCurve(
            strategy_id="weekend-arb",
            dates=dates,
            nav=navs,
        )

    # ── macro-6cycle: placeholder — real NAV built via async_build_macro_6cycle_nav ──

    def _nav_macro_6cycle(self) -> NavCurve | None:
        return None  # Handled by async function below

    # ── cn-us-hk-timing: weight-based reconstruction ────────

    def _nav_cn_us_hk_timing(self) -> NavCurve | None:
        base = os.getenv(
            "CN_US_HK_TIMING_DIR",
            "/Users/xinghuazhang/ygr-project/资产配置监控/实盘/中美港股仓位择时-每日汇报",
        )
        csv_file = os.path.join(
            base,
            "output_data/index_timing/mas_timing/weight_index_ma_timing_us_hk_cn_mix_0.75_0.25_0.0_0.0_v0.42.csv",
        )
        if not os.path.exists(csv_file):
            return None
        df = pd.read_csv(csv_file, encoding="utf-8-sig")
        if df.empty:
            return None

        # Get unique dates
        dates = sorted(df["date"].unique())
        date_strs = [f"{str(d)[:4]}-{str(d)[4:6]}-{str(d)[6:8]}" for d in dates]

        # Placeholder NAV - needs price data for actual calculation
        navs = [1.0] * len(dates)

        return NavCurve(
            strategy_id="cn-us-hk-timing",
            dates=date_strs,
            nav=navs,
        )

    # ── us-fusion: holdings-based reconstruction ─────────────

    def _nav_us_fusion(self) -> NavCurve | None:
        path = os.getenv(
            "US_FUSION_DIR",
            "/Users/xinghuazhang/ygr-project/资产配置监控/实盘/美股实盘/美股融合策略实盘/output/美股动量策略研究",
        )
        history_file = os.path.join(path, "fusion_daily_signal_history.jsonl")
        if not os.path.exists(history_file):
            return None

        records = []
        with open(history_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass

        if not records:
            return None

        dates = []
        navs = []
        nav = 1.0
        for rec in records:
            ts = rec.get("timestamp", "")[:10]
            spy_date = rec.get("spy_latest_date", "")
            dt = spy_date or ts
            if dt:
                dates.append(dt)
                navs.append(round(nav, 6))

        if not dates:
            return None

        return NavCurve(
            strategy_id="us-fusion",
            dates=dates,
            nav=navs if navs else [1.0],
        )

    # ── csi500-timing: price-based reconstruction ────────────

    def _nav_csi500_timing(self) -> NavCurve | None:
        data_dir = os.getenv(
            "CSI500_TIMING_DIR",
            "/Users/xinghuazhang/ygr-project/资产配置监控/实盘_unzip/实盘/ETF实盘代码/data",
        )
        # Try to find the latest signal JSON from scheduler
        scheduler_out = os.path.join(
            os.getenv("STRATEGY_DATA_DIR", data_dir),
            "../output/csi500_timing/latest_signal.json",
        )
        scheduler_out = os.path.normpath(scheduler_out)

        # Try to build NAV from ETF price file
        etf_file = None
        for name in ["512890_SH_etf.csv", "399673_SZ.csv"]:
            p = os.path.join(data_dir, name)
            if os.path.exists(p):
                etf_file = p
                break

        if not etf_file:
            return None

        df = pd.read_csv(etf_file, encoding="utf-8-sig")
        if df.empty or len(df) < 2:
            return None

        # Use close column for NAV
        close_col = None
        for col in ["close", "收盘价", "CLOSE"]:
            if col in df.columns:
                close_col = col
                break
        if not close_col:
            # Try 2nd column as fallback
            close_col = df.columns[1] if len(df.columns) > 1 else None
        if not close_col:
            return None

        date_col = None
        for col in ["trade_date", "日期", "TRADE_DATE", df.columns[0]]:
            if col in df.columns:
                date_col = col
                break
        if not date_col:
            date_col = df.columns[0]

        closes = df[close_col].astype(float).values
        nav = closes / closes[0]

        dates_raw = df[date_col].astype(str).tolist()
        dates = [d[:10] if len(d) >= 10 else d for d in dates_raw]

        return NavCurve(
            strategy_id="csi500-timing",
            dates=dates,
            nav=[round(float(v), 6) for v in nav],
        )

    # ── spmo-usmv-64: Oracle SPX momentum timing reconstruction ──

    _SPMO_USMV_PARAMS = {
        "bench": "SPX.GI",
        "ma_long": [63, 126, 189, 252, 378],
        "ma_short": [5, 10, 15, 20, 40],
        "vol_len": 42,
        "vol_th": 0.19,
    }

    def _nav_spmo_usmv_64(self) -> NavCurve | None:
        """Reconstruct NAV for SPMO/USMV 6:4 using SPX momentum timing."""
        p = self._SPMO_USMV_PARAMS
        from app.services.legacy_signal_parser import signal_parser
        df = signal_parser._fetch_index_close(p["bench"], start_date="20230101")
        if df is None or len(df) < 100:
            return None

        prices = pd.Series(df["CLOSE"].values, index=df["TRADE_DATE"].values, dtype=float).sort_index()
        daily_ret = prices.pct_change().dropna()

        vol = daily_ret.rolling(p["vol_len"]).std() * np.sqrt(252)

        nav = 1.0
        navs = []
        dates = []

        for i in range(max(p["vol_len"], max(p["ma_long"])), len(prices)):
            if i >= len(daily_ret) + 1:
                break
            current_vol = vol.iloc[i - 1] if i - 1 < len(vol) else None
            if pd.isna(current_vol):
                continue

            # Compute momentum at this point
            if current_vol < p["vol_th"]:
                # Low vol regime: use long momentum
                mmt_vals = []
                for period in p["ma_long"]:
                    if i > period:
                        mmt_vals.append(prices.iloc[i] / prices.iloc[i - period] - 1)
                weight = sum(1 for v in mmt_vals if v > 0) / len(mmt_vals) if mmt_vals else 0
            else:
                # High vol regime: use short momentum
                mmt_vals = []
                for period in p["ma_short"]:
                    if i > period:
                        mmt_vals.append(prices.iloc[i] / prices.iloc[i - period] - 1)
                weight = sum(1 for v in mmt_vals if v > 0) / len(mmt_vals) if mmt_vals else 0

            # Portfolio daily return = weight * SPX daily return (SPMO ~ SPX beta * 0.6 + USMV ~ SPX beta * 0.4 ≈ SPX)
            port_ret = weight * daily_ret.iloc[i - 1]
            nav *= (1 + port_ret)

            dt = prices.index[i]
            dt_str = str(dt.date()) if hasattr(dt, 'date') else str(dt)[:10]
            dates.append(dt_str)
            navs.append(round(nav, 6))

        if not dates:
            return None

        return NavCurve(
            strategy_id="spmo-usmv-64",
            dates=dates,
            nav=navs,
        )


nav_builder = NavBuilder()


async def async_build_macro_6cycle_nav() -> NavCurve | None:
    """Build macro-6cycle NAV using weight files + PG ETF prices."""
    weight_dir = os.path.join(_BASE, "output/macro_cycle_rp/weight")
    pattern = os.path.join(weight_dir, "weights_macro_cycle_rp_etf_*.csv")
    files = glob.glob(pattern)
    # WUKONG: 移植时删除
    wukong_dir = "/Users/xinghuazhang/ygr-project/wukong-git/quant_code_product/实盘代码-20260520/实盘代码/output/macro_cycle_rp/weight"
    wukong_pattern = os.path.join(wukong_dir, "weights_macro_cycle_rp_etf_*.csv")
    files.extend(glob.glob(wukong_pattern))
    files = sorted(files, key=lambda f: os.path.basename(f))
    if not files:
        return None

    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f, encoding="utf-8-sig")
            dfs.append(df)
        except Exception:
            pass
    if not dfs:
        return None

    all_df = pd.concat(dfs, ignore_index=True)
    all_df = all_df.drop_duplicates(subset=["date", "windcode"], keep="last")
    all_df = all_df.sort_values("date")

    pivot = all_df.pivot_table(index="date", columns="windcode", values="weight", fill_value=0)
    pivot = pivot.sort_index()

    tickers = list(pivot.columns)

    # Load ETF prices from PG
    from app.db.repository import load_prices
    prices = await load_prices(tickers)
    if prices is None or prices.empty:
        return None

    # Build daily portfolio NAV between rebalance dates
    rebalance_dates = sorted(pivot.index.tolist())
    nav = 1.0
    result_dates = []
    result_navs = []

    for i in range(len(rebalance_dates)):
        d_start = rebalance_dates[i]
        d_end = rebalance_dates[i + 1] if i + 1 < len(rebalance_dates) else None
        weights_row = pivot.loc[d_start]

        ds = str(d_start)
        ds_fmt = f"{ds[:4]}-{ds[4:6]}-{ds[6:8]}"
        if d_end is not None:
            de = str(d_end)
            de_fmt = f"{de[:4]}-{de[4:6]}-{de[6:8]}"
        else:
            # Last rebalance: extend to latest available price date
            de_fmt = str(prices.index[-1].date()) if hasattr(prices.index[-1], 'date') else str(prices.index[-1])[:10]

        # Get daily prices for this period
        mask = (prices.index >= ds_fmt) & (prices.index <= de_fmt)
        period_prices = prices.loc[mask]
        if period_prices.empty:
            continue

        # Calculate daily portfolio returns using weights
        for j in range(1, len(period_prices)):
            day_ret = 0.0
            valid_weight_sum = 0.0
            for t in tickers:
                w = float(weights_row.get(t, 0))
                if w <= 0 or t not in period_prices.columns:
                    continue
                p_today = period_prices[t].iloc[j]
                p_prev = period_prices[t].iloc[j - 1]
                if pd.notna(p_today) and pd.notna(p_prev) and p_prev > 0:
                    day_ret += w * (p_today - p_prev) / p_prev
                    valid_weight_sum += w

            # Re-normalize when some tickers have NaN prices
            if valid_weight_sum > 0 and valid_weight_sum < 0.99:
                day_ret *= sum(float(weights_row.get(t, 0)) for t in tickers) / valid_weight_sum

            nav *= (1 + day_ret)
            idx = period_prices.index[j]
            dt_str = str(idx.date()) if hasattr(idx, 'date') else str(idx)[:10]
            result_dates.append(dt_str)
            result_navs.append(round(nav, 6))

    if not result_dates:
        return None

    return NavCurve(
        strategy_id="macro-6cycle",
        dates=result_dates,
        nav=result_navs,
    )
