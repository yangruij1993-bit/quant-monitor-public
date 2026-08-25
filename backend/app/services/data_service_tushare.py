"""
Tushare data service for A-share ETF daily prices.
Uses fund_daily (raw close) + fund_adj (adjustment factor) and applies
forward-adjustment so series is continuous across splits/dividends.

Pattern follows standard Tushare fund_daily + fund_adj forward-adjustment.
"""

import os
import logging
from typing import Optional

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")
_ts_pro = None


def _get_pro():
    global _ts_pro
    if _ts_pro is None:
        if not _TUSHARE_TOKEN:
            logger.warning("TUSHARE_TOKEN not configured")
            return None
        try:
            import tushare as ts
        except ImportError:
            logger.warning("tushare not installed (pip install tushare); skipping A-share refresh")
            return None
        ts.set_token(_TUSHARE_TOKEN)
        _ts_pro = ts.pro_api()
    return _ts_pro


class TushareDataService:
    """Fetches A-share ETF forward-adjusted daily close from tushare."""

    def __init__(self):
        self.token = _TUSHARE_TOKEN

    def get_prices(
        self,
        tickers: list[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """Fetch forward-adjusted close prices for A-share ETFs.

        Args:
            tickers: list of wind-style codes like '510050.SH', '159915.SZ'
            start_date: 'YYYYMMDD' string or None
            end_date: 'YYYYMMDD' string or None

        Returns:
            DataFrame indexed by date (Timestamp), columns = tickers, values = adj_close
        """
        pro = _get_pro()
        if pro is None:
            return pd.DataFrame()

        today = pd.Timestamp.today().strftime("%Y%m%d")
        end = end_date or today
        # Default start: far back enough for full history on first pull
        start = start_date or "20100101"

        frames: dict[str, pd.Series] = {}
        for code in tickers:
            try:
                daily = pro.fund_daily(
                    ts_code=code, start_date=start, end_date=end
                )
                if daily is None or daily.empty:
                    logger.warning(f"tushare fund_daily empty for {code}")
                    continue

                adj = pro.fund_adj(
                    ts_code=code, start_date=start, end_date=end
                )
                if adj is None or adj.empty:
                    logger.warning(f"tushare fund_adj empty for {code}, using raw close")
                    series = (
                        daily.set_index("trade_date")["close"]
                        .sort_index()
                        .astype(float)
                    )
                else:
                    daily_s = daily.set_index("trade_date")["close"]
                    adj_s = adj.set_index("trade_date")["adj_factor"]
                    # align on trade_date
                    df = pd.concat([daily_s, adj_s], axis=1, join="inner")
                    df.columns = ["close", "adj_factor"]
                    df = df.sort_index()
                    latest_adj = df["adj_factor"].iloc[-1]
                    df["adj_close"] = df["close"] * df["adj_factor"] / latest_adj
                    series = df["adj_close"].astype(float)

                # convert index YYYYMMDD -> Timestamp
                series.index = pd.to_datetime(series.index, format="%Y%m%d")
                frames[code] = series
            except Exception as e:
                logger.error(f"tushare fetch failed for {code}: {e}")
                continue

        if not frames:
            return pd.DataFrame()

        pivot = pd.DataFrame(frames)
        pivot = pivot.sort_index()
        # Ensure all requested tickers are present as columns
        for t in tickers:
            if t not in pivot.columns:
                pivot[t] = float("nan")
        return pivot[tickers].astype(float)


tushare_data_service = TushareDataService()
