"""
data_loader.py — Historical Market Data Acquisition.

Downloads OHLCV data using the Yahoo Finance API for all specified assets
and timeframes, caching the raw results to ensure reproducible backtesting.
"""

import logging
import yfinance as yf
import pandas as pd
from pathlib import Path
from typing import Dict, Any

from .config import ASSETS, TIMEFRAMES, DATA_RAW_DIR

log = logging.getLogger(__name__)


def download_data() -> Dict[str, Dict[str, pd.DataFrame]]:
    """
    Downloads and caches historical OHLCV data.

    Returns
    -------
    Dict[str, Dict[str, pd.DataFrame]]
        A nested dictionary mapping Asset -> Timeframe -> pd.DataFrame.
    """
    data_store: Dict[str, Dict[str, pd.DataFrame]] = {}

    for asset, ticker in ASSETS.items():
        data_store[asset] = {}
        for tf, tf_params in TIMEFRAMES.items():
            interval = tf_params["interval"]
            lookback = tf_params["lookback_days"]

            cache_file: Path = DATA_RAW_DIR / f"{asset}_{tf}.csv"

            if cache_file.exists():
                df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
                data_store[asset][tf] = df
                log.info(
                    f"Loaded cached data: {asset} ({tf}) - {len(df)} bars")
                continue

            log.info(
                f"Downloading {asset} ({tf}) from Yahoo Finance (Ticker: {ticker})...")
            try:
                df = yf.download(
                    tickers=ticker,
                    period=f"{lookback}d",
                    interval=interval,
                    progress=False,
                    auto_adjust=False
                )

                if df is None or df.empty:
                    log.error(f"Failed to download data for {asset} ({tf}).")
                    data_store[asset][tf] = pd.DataFrame()
                    continue

                # Standardize yfinance multi-index columns if present
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel(1)

                # Cache the raw data
                df.to_csv(cache_file)
                data_store[asset][tf] = df
                log.info(
                    f"Successfully downloaded and cached {asset} ({tf}) - {len(df)} bars")

            except Exception as e:
                log.error(f"Error fetching data for {asset} ({tf}): {str(e)}")
                data_store[asset][tf] = pd.DataFrame()

    return data_store
