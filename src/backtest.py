"""
backtest.py — Deterministic Bar-by-Bar Vectorized Execution Engine.

This module simulates the trading environment using historical OHLCV data.
It strictly enforces a T+1 execution model to eliminate look-ahead bias,
where signals generated at the close of bar `t` are executed at the open of bar `t+1`.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Union

from .indicators import add_ema_features
from .strategy import generate_signals


def run_backtest(
    df: pd.DataFrame,
    fast: int,
    slow: int,
    threshold: float,
    initial_equity: float,
) -> Dict[str, Any]:
    """
    Executes a single parameter combination backtest over the provided dataset.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV DataFrame with a proper DatetimeIndex.
    fast : int
        The period for the fast-moving average.
    slow : int
        The period for the slow-moving average.
    threshold : float
        The required EMA angle threshold (in degrees) to trigger entry.
    initial_equity : float
        The starting capital for the backtest in nominal currency.

    Returns
    -------
    Dict[str, Any]
        A comprehensive dictionary containing all trade records and aggregate
        performance metrics (e.g., Sharpe ratio, maximum drawdown, total profit).
    """
    if df is None or len(df) < max(fast, slow) + 10:
        return _empty_metrics(fast, slow, threshold, initial_equity)

    # Calculate indicators
    feat: pd.DataFrame = add_ema_features(df, fast, slow)
    feat = feat.dropna(subset=["ema_fast", "ema_slow", "angle_fast"])

    if len(feat) < 5:
        return _empty_metrics(fast, slow, threshold, initial_equity)

    # Generate deterministic signals
    raw_signals: pd.Series = generate_signals(feat, threshold)

    # Extract numpy arrays for O(1) loop access
    opens: np.ndarray = feat["Open"].values
    closes: np.ndarray = feat["Close"].values
    fast_ema: np.ndarray = feat["ema_fast"].values
    slow_ema: np.ndarray = feat["ema_slow"].values
    dates: pd.DatetimeIndex = feat.index
    sigs: np.ndarray = raw_signals.values

    # Simulation State Variables
    equity: float = initial_equity
    position: int = 0         # 0=flat, 1=long, -1=short
    entry_px: float = 0.0
    entry_dt: Union[pd.Timestamp, None] = None
    entry_qty: float = 0.0

    trades: List[Dict[str, Any]] = []
    equity_curve: List[float] = [equity]

    # Bar-by-bar execution loop
    for i in range(1, len(feat)):
        prev_sig: int = sigs[i - 1]
        prev_f: float = fast_ema[i - 1]
        prev_s: float = slow_ema[i - 1]
        open_px: float = opens[i]
        dt: pd.Timestamp = dates[i]

        # ── Exit Logic Evaluation ──────────────────────────────
        if position == 1:
            # Long Exit: Fast EMA crosses below Slow EMA (Trend Reversal)
            if prev_f < prev_s:
                pnl = (open_px - entry_px) / entry_px * \
                    equity if entry_px > 0 else 0.0
                equity += pnl
                trades.append(_trade_record(entry_dt, dt, entry_px,
                              open_px, entry_qty, pnl, "LONG"))
                position = 0

        elif position == -1:
            # Short Exit: Fast EMA crosses above Slow EMA
            if prev_f > prev_s:
                pnl = (entry_px - open_px) / entry_px * equity if entry_px > 0 else 0.0
                equity += pnl
                trades.append(_trade_record(entry_dt, dt, entry_px,
                              open_px, entry_qty, pnl, "SHORT"))
                position = 0

        # ── Entry Logic Evaluation ─────────────────────────────
        if position == 0:
            if prev_sig == 1:
                position = 1
                entry_px = open_px
                entry_dt = dt
                entry_qty = equity / open_px if open_px > 0 else 0.0

            elif prev_sig == -1:
                position = -1
                entry_px = open_px
                entry_dt = dt
                entry_qty = equity / open_px if open_px > 0 else 0.0

        equity_curve.append(equity)

    # ── Liquidation of Open Positions at Terminal Bar ────────
    if position != 0 and len(feat) > 0:
        last_px: float = closes[-1]
        last_dt: pd.Timestamp = dates[-1]

        if position == 1:
            pnl = (last_px - entry_px) / entry_px * equity if entry_px > 0 else 0.0
        else:
            pnl = (entry_px - last_px) / entry_px * equity if entry_px > 0 else 0.0

        equity += pnl
        trades.append(_trade_record(
            entry_dt, last_dt, entry_px, last_px,
            entry_qty, pnl, "LONG" if position == 1 else "SHORT"
        ))

    return _compute_metrics(trades, equity_curve, initial_equity, fast, slow, threshold)


def _trade_record(
    entry_dt: pd.Timestamp,
    exit_dt: pd.Timestamp,
    entry_px: float,
    exit_px: float,
    qty: float,
    pnl: float,
    direction: str
) -> Dict[str, Any]:
    """Formats a single executed trade into a standardized dictionary."""
    ret_pct: float = (pnl / (abs(qty * entry_px)) *
                      100.0) if (qty > 0 and entry_px > 0) else 0.0
    return {
        "entry_date":  entry_dt,
        "exit_date":   exit_dt,
        "direction":   direction,
        "entry_price": round(float(entry_px), 6),
        "exit_price":  round(float(exit_px), 6),
        "qty":         round(float(qty), 6),
        "pnl":         round(float(pnl), 4),
        "return_pct":  round(float(ret_pct), 4),
    }


def _compute_metrics(
    trades: List[Dict[str, Any]],
    equity_curve: List[float],
    initial_equity: float,
    fast: int,
    slow: int,
    threshold: float
) -> Dict[str, Any]:
    """Calculates aggregate performance statistics (Sharpe, Drawdown, Profit Factor)."""
    if not trades:
        return _empty_metrics(fast, slow, threshold, initial_equity)

    wins: List[Dict[str, Any]] = [t for t in trades if t["pnl"] > 0]
    losses: List[Dict[str, Any]] = [t for t in trades if t["pnl"] <= 0]

    gross_profit: float = sum(t["pnl"] for t in wins)
    gross_loss: float = abs(sum(t["pnl"] for t in losses))

    profit_factor: float = (
        gross_profit / gross_loss) if gross_loss > 0 else float('inf')
    win_rate: float = (len(wins) / len(trades) * 100.0) if trades else 0.0
    total_pnl: float = sum(t["pnl"] for t in trades)

    # Maximum Drawdown Calculation
    eq_ary: np.ndarray = np.array(equity_curve)
    peaks: np.ndarray = np.maximum.accumulate(eq_ary)
    drawdowns: np.ndarray = (peaks - eq_ary) / peaks
    max_dd: float = float(np.max(drawdowns) *
                          100.0) if len(drawdowns) > 0 else 0.0

    # Sharpe Ratio (Daily Approximation)
    eq_series: pd.Series = pd.Series(equity_curve)
    rets: pd.Series = eq_series.pct_change().dropna()
    mean_ret: float = float(rets.mean())
    std_ret: float = float(rets.std())
    sharpe: float = 0.0
    if std_ret != 0 and not np.isnan(std_ret):
        # Approx annualized for hourly/minute data
        sharpe = (mean_ret / std_ret) * np.sqrt(252 * 24)

    return {
        "trades": trades,
        "total_trades": len(trades),
        "long_trades": sum(1 for t in trades if t["direction"] == "LONG"),
        "short_trades": sum(1 for t in trades if t["direction"] == "SHORT"),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": round(win_rate, 2),
        "total_profit": round(total_pnl, 2),
        "avg_profit": round(total_pnl / len(trades), 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else 999.9,
        "sharpe_ratio": round(sharpe, 4),
        "max_drawdown": round(max_dd, 2),
        "final_equity": round(equity_curve[-1], 2),
        "fast_ema": fast,
        "slow_ema": slow,
        "ema_pair": f"EMA({fast},{slow})",
        "angle_threshold": threshold,
    }


def _empty_metrics(fast: int, slow: int, threshold: float, initial_equity: float) -> Dict[str, Any]:
    """Returns a zeroed metrics dictionary for parameter sets that produce no trades."""
    return {
        "trades": [],
        "total_trades": 0,
        "long_trades": 0,
        "short_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "win_rate": 0.0,
        "total_profit": 0.0,
        "avg_profit": 0.0,
        "profit_factor": 0.0,
        "sharpe_ratio": 0.0,
        "max_drawdown": 0.0,
        "final_equity": initial_equity,
        "fast_ema": fast,
        "slow_ema": slow,
        "ema_pair": f"EMA({fast},{slow})",
        "angle_threshold": threshold,
    }
