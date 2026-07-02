"""
strategy.py — Signal Generation Logic via EMA Angle and Alignment Filtering.

This module evaluates the mathematically derived EMA and Angle features to
generate deterministic Long/Short signals. 

Entry Logic:
-----------
A Long (+1) signal is generated if:
    1. EMA_Fast > EMA_Slow (Directional alignment)
    2. Angle_Fast >= +threshold (Strong upward momentum)
    3. Angle_Slow >= 0 (Macro trend confirmation)

A Short (-1) signal is generated if:
    1. EMA_Fast < EMA_Slow
    2. Angle_Fast <= -threshold
    3. Angle_Slow <= 0

Exit logic is handled dynamically by the backtesting engine (crossover detection).
"""
import pandas as pd


def generate_signals(df: pd.DataFrame, threshold: float) -> pd.Series:
    """
    Evaluates geometric features to generate quantitative trading signals.

    Parameters
    ----------
    df : pd.DataFrame
        The OHLCV dataset augmented with EMA, slope, and angle columns.
    threshold : float
        The minimum acceptable angle (in degrees) required to trigger a signal.
        For short signals, the negative equivalent is evaluated.

    Returns
    -------
    pd.Series
        A pandas Series of integers representing trade states on each bar:
        +1 indicates a Long entry condition.
        -1 indicates a Short entry condition.
         0 indicates a Neutral (flat) condition.
    """
    fast: pd.Series = df["ema_fast"]
    slow: pd.Series = df["ema_slow"]
    fast_angle: pd.Series = df["angle_fast"]
    slow_angle: pd.Series = df["angle_slow"]

    # Evaluate Long conditions
    long_raw: pd.Series = (
        (fast > slow) &
        (fast_angle >= threshold) &
        (slow_angle >= 0)
    )

    # Evaluate Short conditions
    short_raw: pd.Series = (
        (fast < slow) &
        (fast_angle <= -threshold) &
        (slow_angle <= 0)
    )

    # Initialize neutral signal array
    signal: pd.Series = pd.Series(0, index=df.index, dtype=int)

    # Apply conditions
    signal[long_raw] = 1
    signal[short_raw] = -1

    return signal
