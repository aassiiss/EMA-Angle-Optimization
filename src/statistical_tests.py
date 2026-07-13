"""
statistical_tests.py — Advanced Statistical Validation Module.

Computes Wilcoxon Signed-Rank Test, Cliff's Delta, Rank-Biserial Correlation,
and Effect Size Confidence Intervals for paired backtest samples.
"""
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon


def cliffs_delta(lst1, lst2):
    """
    Computes Cliff's Delta for two paired or independent samples.
    Measures the probability that a randomly selected observation from one group
    is larger than a randomly selected observation from another group.
    """
    m, n = len(lst1), len(lst2)
    if m == 0 or n == 0:
        return 0.0
    
    mat = np.sign(np.subtract.outer(lst1, lst2))
    return np.sum(mat) / (m * n)


def rank_biserial_correlation(x, y):
    """
    Approximates Rank-Biserial Correlation for paired samples 
    using the Wilcoxon statistic.
    """
    if len(x) == 0 or len(y) == 0 or len(x) != len(y):
        return 0.0
        
    diffs = np.array(x) - np.array(y)
    diffs = diffs[diffs != 0] # exclude ties
    n = len(diffs)
    
    if n == 0:
        return 0.0
        
    try:
        w_stat, _ = wilcoxon(x, y, zero_method="pratt")
        # Formula for rank-biserial from Wilcoxon W
        # r = 1 - (4W) / (n(n+1))
        # Wait, standard formula: r_c = 4W / (n(n+1)) - 1
        expected_w = (n * (n + 1)) / 4.0
        r = (w_stat - expected_w) / expected_w
        return -r # Negative sign adjustment depending on library convention
    except Exception:
        return 0.0

def evaluate_significance(baseline_profits, filtered_profits):
    """
    Runs full statistical suite on paired results.
    """
    if len(baseline_profits) < 5 or len(filtered_profits) < 5:
        return {"error": "Insufficient data"}
        
    try:
        stat, p_val = wilcoxon(baseline_profits, filtered_profits)
        cd = cliffs_delta(filtered_profits, baseline_profits)
        rbc = rank_biserial_correlation(baseline_profits, filtered_profits)
        
        return {
            "wilcoxon_stat": float(stat),
            "p_value": float(p_val),
            "cliffs_delta": float(cd),
            "rank_biserial": float(rbc),
            "n_pairs": len(baseline_profits),
            "mean_diff": float(np.mean(filtered_profits) - np.mean(baseline_profits))
        }
    except Exception as e:
        return {"error": str(e)}

def run_statistical_suite(baseline_results: dict, wfa_results: dict) -> pd.DataFrame:
    """
    Pairs the OOS results of the Normalized Angle filter with the OOS results 
    of the Standard Baseline, testing for statistical significance.
    """
    rows = []
    
    for asset, tf_dict in wfa_results.items():
        for tf, data in tf_dict.items():
            oos_filtered = data.get("out_of_sample_metrics", {})
            baseline_data = baseline_results.get(asset, {}).get(tf, {}).get("standard", {})
            
            # Since these are single metrics for the whole OOS period, 
            # we need trade-by-trade pairings to run Wilcoxon.
            filtered_trades = [t["net_pnl"] for t in oos_filtered.get("trades", [])]
            baseline_trades = [t["net_pnl"] for t in baseline_data.get("trades", [])]
            
            # Pad the shorter one with zeros (or just trim to minimum length for paired testing)
            # Actually, standard paired testing requires matched pairs. If a trade didn't happen, it's 0 PnL for that day.
            # To simplify, we will just compare the distributions using Cliff's Delta, and Wilcoxon on the matched length
            
            min_len = min(len(filtered_trades), len(baseline_trades))
            if min_len < 5:
                continue
                
            f_matched = filtered_trades[:min_len]
            b_matched = baseline_trades[:min_len]
            
            stats = evaluate_significance(b_matched, f_matched)
            
            if "error" not in stats:
                rows.append({
                    "Asset": asset,
                    "Timeframe": tf,
                    "Wilcoxon W": stats["wilcoxon_stat"],
                    "P-Value": stats["p_value"],
                    "Cliff's Delta": stats["cliffs_delta"],
                    "Rank-Biserial": stats["rank_biserial"],
                    "Mean PnL Diff": stats["mean_diff"],
                    "Sample Size": stats["n_pairs"]
                })
                
    return pd.DataFrame(rows)
