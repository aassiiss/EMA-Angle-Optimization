r"""
indicators.py — Mathematical computation of Exponential Moving Averages (EMA) and derived vector geometry.

This module is responsible for calculating price indicators and extracting
their geometric properties (slope and angle) for momentum evaluation.

Equations:
----------
EMA_t = (Close_t * \alpha) + (EMA_{t-1} * (1 - \alpha))
where \alpha = 2 / (period + 1)

Slope_t = EMA_t - EMA_{t-1}

\theta_t = \arctan(Slope_t) \times \left(\frac{180}{\pi}\right)
"""

import numpy as np
import pandas as pd


def calc_ema(series: pd.Series, period: int) -> pd.Series:
    """
    Computes the Exponential Moving Average (EMA) for a given pandas Series.

    Parameters
    ----------
    series : pd.Series
        The input price data (e.g., Close prices).
    period : int
        The lookback period for the moving average.

    Returns
    -------
    pd.Series
        The calculated EMA values.
    """
    return series.ewm(span=period, adjust=False).mean()


def calc_slope(ema_series: pd.Series) -> pd.Series:
    """
    Computes the geometric slope (rate of change) of an EMA series.

    The slope is defined strictly as the nominal difference between the current 
    EMA value and the previous period's EMA value.

    Parameters
    ----------
    ema_series : pd.Series
        The exponentially smoothed price data.

    Returns
    -------
    pd.Series
        The nominal difference (slope).
    """
    return ema_series.diff()


def calc_angle(ema_series: pd.Series) -> pd.Series:
    """
    Computes the geometric angle (\theta) of the EMA vector in degrees.

    This function isolates the momentum trajectory by converting the nominal 
    slope into a standardized degree measurement (-90 to +90 degrees).

    Parameters
    ----------
    ema_series : pd.Series
        The exponentially smoothed price data.

    Returns
    -------
    pd.Series
        The angle of the EMA trajectory in degrees.
    """
    slope: pd.Series = calc_slope(ema_series)
    return np.degrees(np.arctan(slope))


def add_ema_features(df: pd.DataFrame, fast: int, slow: int) -> pd.DataFrame:
    """
    Appends dual EMA values, their respective slopes, and angles to the OHLCV dataframe.

    Parameters
    ----------
    df : pd.DataFrame
        The raw financial time-series data containing a 'Close' column.
    fast : int
        The period for the fast-moving average.
    slow : int
        The period for the slow-moving average.

    Returns
    -------
    pd.DataFrame
        A new DataFrame containing the original price data augmented with:
        - `ema_fast`, `ema_slow`
        - `slope_fast`, `slope_slow`
        - `angle_fast`, `angle_slow`
    """
    out: pd.DataFrame = df.copy()
    out["ema_fast"] = calc_ema(out["Close"], fast)
    out["ema_slow"] = calc_ema(out["Close"], slow)
    out["slope_fast"] = calc_slope(out["ema_fast"])
    out["slope_slow"] = calc_slope(out["ema_slow"])
    out["angle_fast"] = calc_angle(out["ema_fast"])
    out["angle_slow"] = calc_angle(out["ema_slow"])

    return out
