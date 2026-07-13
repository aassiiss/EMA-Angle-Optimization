"""
backtest.py — Deterministic Bar-by-Bar Vectorized Execution Engine.

This module simulates the trading environment using historical OHLCV data.
It strictly enforces a T+1 execution model to eliminate look-ahead bias,
where signals generated at the close of bar `t` are executed at the open of bar `t+1`.
Now includes realistic transaction costs, slippage, and advanced risk metrics.
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
    commission_pct: float = 0.0,
    slippage_pct: float = 0.0,
    fixed_commission: float = 0.0,
    baseline_mode: str = "standard"
) -> Dict[str, Any]:
    if df is None or len(df) < max(fast, slow) + 10:
        return _empty_metrics(fast, slow, threshold, initial_equity, baseline_mode)

    # Calculate indicators
    feat: pd.DataFrame = add_ema_features(df, fast, slow)
    feat = feat.dropna()

    if len(feat) < 5:
        return _empty_metrics(fast, slow, threshold, initial_equity, baseline_mode)

    # Generate deterministic signals based on the mode
    raw_signals: pd.Series = generate_signals(feat, threshold, mode=baseline_mode)

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
    
    total_commission_paid: float = 0.0
    total_slippage_paid: float = 0.0

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
                exit_px = open_px * (1 - slippage_pct)
                slippage_cost = (open_px - exit_px) * entry_qty
                comm_cost = (exit_px * entry_qty * commission_pct) + fixed_commission
                
                gross_pnl = (open_px - entry_px) * entry_qty
                net_pnl = (exit_px - entry_px) * entry_qty - comm_cost
                
                total_commission_paid += comm_cost
                total_slippage_paid += slippage_cost
                equity += net_pnl
                
                trades.append(_trade_record(entry_dt, dt, entry_px, exit_px, entry_qty, net_pnl, gross_pnl, "LONG"))
                position = 0

        elif position == -1:
            # Short Exit: Fast EMA crosses above Slow EMA
            if prev_f > prev_s:
                exit_px = open_px * (1 + slippage_pct)
                slippage_cost = (exit_px - open_px) * entry_qty
                comm_cost = (exit_px * entry_qty * commission_pct) + fixed_commission
                
                gross_pnl = (entry_px - open_px) * entry_qty
                net_pnl = (entry_px - exit_px) * entry_qty - comm_cost
                
                total_commission_paid += comm_cost
                total_slippage_paid += slippage_cost
                equity += net_pnl
                
                trades.append(_trade_record(entry_dt, dt, entry_px, exit_px, entry_qty, net_pnl, gross_pnl, "SHORT"))
                position = 0

        # ── Entry Logic Evaluation ─────────────────────────────
        if position == 0:
            if prev_sig == 1:
                position = 1
                entry_px = open_px * (1 + slippage_pct)
                entry_qty = (equity * 0.99) / entry_px if entry_px > 0 else 0.0
                
                slippage_cost = (entry_px - open_px) * entry_qty
                comm_cost = (entry_px * entry_qty * commission_pct) + fixed_commission
                equity -= comm_cost
                
                total_commission_paid += comm_cost
                total_slippage_paid += slippage_cost
                entry_dt = dt

            elif prev_sig == -1:
                position = -1
                entry_px = open_px * (1 - slippage_pct)
                entry_qty = (equity * 0.99) / entry_px if entry_px > 0 else 0.0
                
                slippage_cost = (open_px - entry_px) * entry_qty
                comm_cost = (entry_px * entry_qty * commission_pct) + fixed_commission
                equity -= comm_cost
                
                total_commission_paid += comm_cost
                total_slippage_paid += slippage_cost
                entry_dt = dt

        equity_curve.append(equity)

    # ── Liquidation of Open Positions at Terminal Bar ────────
    if position != 0 and len(feat) > 0:
        last_px: float = closes[-1]
        last_dt: pd.Timestamp = dates[-1]

        if position == 1:
            exit_px = last_px * (1 - slippage_pct)
            gross_pnl = (last_px - entry_px) * entry_qty
            net_pnl = (exit_px - entry_px) * entry_qty - (exit_px * entry_qty * commission_pct + fixed_commission)
        else:
            exit_px = last_px * (1 + slippage_pct)
            gross_pnl = (entry_px - last_px) * entry_qty
            net_pnl = (entry_px - exit_px) * entry_qty - (exit_px * entry_qty * commission_pct + fixed_commission)

        equity += net_pnl
        trades.append(_trade_record(
            entry_dt, last_dt, entry_px, exit_px,
            entry_qty, net_pnl, gross_pnl, "LONG" if position == 1 else "SHORT"
        ))

    return _compute_metrics(trades, equity_curve, initial_equity, fast, slow, threshold, total_commission_paid, total_slippage_paid, baseline_mode)


def _trade_record(
    entry_dt: pd.Timestamp,
    exit_dt: pd.Timestamp,
    entry_px: float,
    exit_px: float,
    qty: float,
    net_pnl: float,
    gross_pnl: float,
    direction: str
) -> Dict[str, Any]:
    ret_pct: float = (net_pnl / (abs(qty * entry_px)) * 100.0) if (qty > 0 and entry_px > 0) else 0.0
    holding_time = (exit_dt - entry_dt).total_seconds() / 3600.0 # in hours
    return {
        "entry_date":  entry_dt,
        "exit_date":   exit_dt,
        "direction":   direction,
        "entry_price": round(float(entry_px), 6),
        "exit_price":  round(float(exit_px), 6),
        "qty":         round(float(qty), 6),
        "gross_pnl":   round(float(gross_pnl), 4),
        "net_pnl":     round(float(net_pnl), 4),
        "return_pct":  round(float(ret_pct), 4),
        "holding_time_hrs": round(float(holding_time), 2),
    }


def _compute_metrics(
    trades: List[Dict[str, Any]],
    equity_curve: List[float],
    initial_equity: float,
    fast: int,
    slow: int,
    threshold: float,
    total_commission_paid: float,
    total_slippage_paid: float,
    baseline_mode: str
) -> Dict[str, Any]:
    if not trades:
        return _empty_metrics(fast, slow, threshold, initial_equity, baseline_mode)

    wins: List[Dict[str, Any]] = [t for t in trades if t["net_pnl"] > 0]
    losses: List[Dict[str, Any]] = [t for t in trades if t["net_pnl"] <= 0]

    gross_profit: float = sum(t["gross_pnl"] for t in wins)
    gross_loss: float = abs(sum(t["gross_pnl"] for t in losses))
    
    net_profit_sum: float = sum(t["net_pnl"] for t in wins)
    net_loss_sum: float = abs(sum(t["net_pnl"] for t in losses))

    profit_factor: float = (net_profit_sum / net_loss_sum) if net_loss_sum > 0 else float('inf')
    win_rate: float = (len(wins) / len(trades) * 100.0) if trades else 0.0
    total_net_pnl: float = sum(t["net_pnl"] for t in trades)
    total_gross_pnl: float = sum(t["gross_pnl"] for t in trades)
    
    avg_trade_net = total_net_pnl / len(trades)
    avg_holding_time = np.mean([t["holding_time_hrs"] for t in trades])

    # Maximum Drawdown Calculation
    eq_ary: np.ndarray = np.array(equity_curve)
    peaks: np.ndarray = np.maximum.accumulate(eq_ary)
    drawdowns: np.ndarray = (peaks - eq_ary) / peaks
    max_dd: float = float(np.max(drawdowns) * 100.0) if len(drawdowns) > 0 else 0.0
    avg_dd: float = float(np.mean(drawdowns[drawdowns > 0]) * 100.0) if len(drawdowns[drawdowns > 0]) > 0 else 0.0

    # Risk Ratios
    eq_series: pd.Series = pd.Series(equity_curve)
    rets: pd.Series = eq_series.pct_change().dropna()
    mean_ret: float = float(rets.mean())
    std_ret: float = float(rets.std())
    downside_std: float = float(rets[rets < 0].std())
    
    annualization_factor = np.sqrt(252 * 24) # Assuming hourly data baseline scaling for comparison
    
    sharpe: float = 0.0
    if std_ret != 0 and not np.isnan(std_ret):
        sharpe = (mean_ret / std_ret) * annualization_factor
        
    sortino: float = 0.0
    if downside_std != 0 and not np.isnan(downside_std):
        sortino = (mean_ret / downside_std) * annualization_factor
        
    calmar: float = 0.0
    annualized_return = ((equity_curve[-1] / initial_equity) ** (1 / max((len(equity_curve) / (252*24)), 1)) - 1) * 100 
    if max_dd > 0:
        calmar = annualized_return / max_dd

    return {
        "trades": trades,
        "total_trades": len(trades),
        "long_trades": sum(1 for t in trades if t["direction"] == "LONG"),
        "short_trades": sum(1 for t in trades if t["direction"] == "SHORT"),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": round(win_rate, 2),
        "total_gross_profit": round(total_gross_pnl, 2),
        "total_net_profit": round(total_net_pnl, 2),
        "avg_trade_net": round(avg_trade_net, 2),
        "expectancy": round(avg_trade_net, 2), 
        "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else 999.9,
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "calmar_ratio": round(calmar, 4),
        "max_drawdown": round(max_dd, 2),
        "avg_drawdown": round(avg_dd, 2),
        "annualized_return": round(annualized_return, 2),
        "final_equity": round(equity_curve[-1], 2),
        "total_commission_paid": round(total_commission_paid, 2),
        "total_slippage_paid": round(total_slippage_paid, 2),
        "avg_holding_time_hrs": round(avg_holding_time, 2),
        "fast_ema": fast,
        "slow_ema": slow,
        "ema_pair": f"EMA({fast},{slow})",
        "angle_threshold": threshold,
        "baseline_mode": baseline_mode
    }


def _empty_metrics(fast: int, slow: int, threshold: float, initial_equity: float, baseline_mode: str) -> Dict[str, Any]:
    return {
        "trades": [],
        "total_trades": 0,
        "long_trades": 0,
        "short_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "win_rate": 0.0,
        "total_gross_profit": 0.0,
        "total_net_profit": 0.0,
        "avg_trade_net": 0.0,
        "expectancy": 0.0,
        "profit_factor": 0.0,
        "sharpe_ratio": 0.0,
        "sortino_ratio": 0.0,
        "calmar_ratio": 0.0,
        "max_drawdown": 0.0,
        "avg_drawdown": 0.0,
        "annualized_return": 0.0,
        "final_equity": initial_equity,
        "total_commission_paid": 0.0,
        "total_slippage_paid": 0.0,
        "avg_holding_time_hrs": 0.0,
        "fast_ema": fast,
        "slow_ema": slow,
        "ema_pair": f"EMA({fast},{slow})",
        "angle_threshold": threshold,
        "baseline_mode": baseline_mode
    }
