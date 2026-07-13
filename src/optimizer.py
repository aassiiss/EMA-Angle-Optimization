"""
optimizer.py — Parameter Optimization, Walk-Forward Analysis, and Regime Detection.

This module orchestrates the complete grid search, executing backtests
across every possible combination of Assets, Timeframes, EMA Pairs, and Angle Thresholds.
It strictly enforces Walk-Forward Analysis (WFA) to prevent optimization bias.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, List

from .config import EMA_PAIRS, ANGLE_THRESHOLDS, ASSETS, TIMEFRAMES, RANK_METRIC
from .config import INITIAL_EQUITY, COMMISSION_PCT, SLIPPAGE_PCT, FIXED_COMMISSION, WFA_TRAIN_SPLIT, BASELINES
from .backtest import run_backtest

log = logging.getLogger(__name__)


def detect_regime(df: pd.DataFrame) -> str:
    """Detects the primary market regime for a given slice of data."""
    if len(df) < 50:
        return "UNKNOWN"
        
    closes = df["Close"]
    sma50 = closes.rolling(50).mean()
    
    # Trend
    if closes.iloc[-1] > sma50.iloc[-1] and closes.iloc[0] < closes.iloc[-1]:
        trend = "BULL"
    elif closes.iloc[-1] < sma50.iloc[-1] and closes.iloc[0] > closes.iloc[-1]:
        trend = "BEAR"
    else:
        trend = "SIDEWAYS"
        
    # Volatility (ATR approx)
    high = df["High"]
    low = df["Low"]
    tr = high - low
    atr = tr.rolling(14).mean()
    atr_pct = (atr / closes) * 100
    
    vol_regime = "HIGH_VOL" if atr_pct.mean() > 1.0 else "LOW_VOL"
    
    return f"{trend}_{vol_regime}"


def run_grid_search_on_slice(df_slice: pd.DataFrame, baseline_mode: str = "norm_angle") -> Dict[Any, Dict[str, Any]]:
    """Runs a grid search on a specific slice of data."""
    results = {}
    for (fast, slow) in EMA_PAIRS:
        for threshold in ANGLE_THRESHOLDS:
            metrics = run_backtest(
                df_slice, fast, slow, threshold, INITIAL_EQUITY,
                COMMISSION_PCT, SLIPPAGE_PCT, FIXED_COMMISSION, baseline_mode
            )
            results[(fast, slow, threshold)] = metrics
    return results


def select_best_parameter(results_dict: Dict[Any, Dict[str, Any]], rank_metric: str) -> tuple:
    """Selects the best parameter tuple based on the ranking metric."""
    best_param = None
    best_val = -float('inf')
    
    # Mapping config keys to metric dict keys
    metric_map = {
        "total_profit": "total_net_profit",
        "sharpe_ratio": "sharpe_ratio",
        "profit_factor": "profit_factor",
        "win_rate": "win_rate"
    }
    
    target_key = metric_map.get(rank_metric, "total_net_profit")
    
    for param, metrics in results_dict.items():
        if metrics.get("total_trades", 0) > 0:
            val = metrics.get(target_key, -float('inf'))
            if val != 999.9 and val > best_val:
                best_val = val
                best_param = param
                
    if best_param is None and len(results_dict) > 0:
        # Fallback to first if all fail
        return list(results_dict.keys())[0]
        
    return best_param


def run_walk_forward_analysis(
    data_store: Dict[str, Dict[str, pd.DataFrame]],
) -> Dict[str, Any]:
    """
    Executes Walk-Forward Analysis across all assets and timeframes.
    Splits data into IS and OOS, optimizes on IS, validates on OOS.
    Also executes regime robustness and baseline comparisons.
    """
    wfa_results = {}
    baseline_results = {}
    regime_results = {}
    
    total_iterations = len(ASSETS) * len(TIMEFRAMES)
    completed = 0

    for asset in ASSETS:
        wfa_results[asset] = {}
        baseline_results[asset] = {}
        regime_results[asset] = {}
        
        for tf in TIMEFRAMES:
            df: pd.DataFrame = data_store.get(asset, {}).get(tf)

            if df is None or len(df) < 100:
                log.warning(f"Insufficient data for {asset} on {tf}. Skipping.")
                continue

            split_idx = int(len(df) * WFA_TRAIN_SPLIT)
            df_is = df.iloc[:split_idx]
            df_oos = df.iloc[split_idx:]
            
            # --- WFA: Optimize on In-Sample (norm_angle only for optimization phase) ---
            is_results = run_grid_search_on_slice(df_is, "norm_angle")
            best_param = select_best_parameter(is_results, RANK_METRIC)
            
            if best_param is None:
                continue
                
            fast, slow, threshold = best_param
            
            # --- WFA: Test on Out-of-Sample ---
            oos_metrics = run_backtest(
                df_oos, fast, slow, threshold, INITIAL_EQUITY,
                COMMISSION_PCT, SLIPPAGE_PCT, FIXED_COMMISSION, "norm_angle"
            )
            
            wfa_results[asset][tf] = {
                "in_sample_best_param": best_param,
                "in_sample_metrics": is_results[best_param],
                "out_of_sample_metrics": oos_metrics
            }
            
            # --- Regimes ---
            regime = detect_regime(df_oos)
            regime_results[asset][tf] = {
                "regime": regime,
                "metrics": oos_metrics
            }
            
            # --- Baselines ---
            baseline_results[asset][tf] = {}
            for mode in BASELINES:
                # We test baselines on the OOS set using the SAME fast/slow parameters, 
                # but with appropriate arbitrary thresholds for ROC and MACD (just using 0 for simplicity if not grid searched)
                base_thresh = 0.0 if mode in ["macd", "linreg", "standard"] else threshold
                base_metrics = run_backtest(
                    df_oos, fast, slow, base_thresh, INITIAL_EQUITY,
                    COMMISSION_PCT, SLIPPAGE_PCT, FIXED_COMMISSION, mode
                )
                baseline_results[asset][tf][mode] = base_metrics

            completed += 1
            log.info(f"WFA Progress: {completed}/{total_iterations} iterations complete.")

    log.info(f"WFA Sweep Complete.")
    return {
        "wfa": wfa_results,
        "baselines": baseline_results,
        "regimes": regime_results
    }


def build_wfa_ranking_table(wfa_results: Dict[str, Dict[str, Dict[str, Any]]]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []

    for asset, tf_dict in wfa_results.items():
        for tf, data in tf_dict.items():
            best_param = data.get("in_sample_best_param")
            if not best_param:
                continue
                
            f, s, thr = best_param
            oos = data.get("out_of_sample_metrics", {})
            
            rows.append({
                "Market": asset,
                "Timeframe": tf,
                "IS Best EMA": f"EMA({f},{s})",
                "IS Best Threshold": thr,
                "OOS Trades": oos.get("total_trades", 0),
                "OOS Win Rate (%)": oos.get("win_rate", 0.0),
                "OOS Net Profit ($)": oos.get("total_net_profit", 0.0),
                "OOS Profit Factor": oos.get("profit_factor", 0.0),
                "OOS Sharpe": oos.get("sharpe_ratio", 0.0),
                "OOS Max Drawdown (%)": oos.get("max_drawdown", 0.0),
            })

    df: pd.DataFrame = pd.DataFrame(rows)
    return df

def build_baseline_comparison_table(baseline_results: Dict[str, Dict[str, Dict[str, Any]]]) -> pd.DataFrame:
    rows = []
    for asset, tf_dict in baseline_results.items():
        for tf, modes in tf_dict.items():
            for mode, m in modes.items():
                rows.append({
                    "Market": asset,
                    "Timeframe": tf,
                    "Baseline Mode": mode,
                    "Trades": m.get("total_trades", 0),
                    "Win Rate (%)": m.get("win_rate", 0.0),
                    "Net Profit ($)": m.get("total_net_profit", 0.0),
                    "Sharpe Ratio": m.get("sharpe_ratio", 0.0),
                })
    return pd.DataFrame(rows)
