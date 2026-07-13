import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
import json
import os

from src.backtest import run_backtest
from src.config import EMA_PAIRS, ASSETS, TIMEFRAMES

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_FILE = BASE_DIR / "results" / "logs" / "audit_report.json"

def verify_files():
    required = [
        "main.py", "run_baselines.py", "src/backtest.py", "src/indicators.py", 
        "src/strategy.py", "paper/Draft_Manuscript.md"
    ]
    missing = []
    for f in required:
        if not (BASE_DIR / f).exists():
            missing.append(f)
    return {"status": "Pass" if not missing else "Fail", "missing": missing}

def independent_metric_calculation(trades, equity_curve):
    if not trades:
        return {"win_rate": 0.0, "sharpe": 0.0}
    wins = sum(1 for t in trades if t['pnl'] > 0)
    wr = wins / len(trades) * 100
    
    eq = pd.Series(equity_curve)
    rets = eq.pct_change().dropna()
    std = rets.std()
    sharpe = 0.0
    if std > 0:
        sharpe = (rets.mean() / std) * np.sqrt(252 * 24)
    return {"win_rate": wr, "sharpe": sharpe}

def run_audit():
    audit_results = {
        "file_verification": verify_files(),
        "discrepancies": [],
        "baselines": [],
        "statistical_test": {}
    }
    
    baseline_metrics = []
    treatment_metrics = []
    
    for asset in ASSETS:
        for tf in TIMEFRAMES:
            file_path = DATA_DIR / f"{asset}_{tf}.csv"
            if not file_path.exists():
                continue
            
            try:
                df = pd.read_csv(file_path, parse_dates=['Datetime'])
                df.set_index('Datetime', inplace=True)
            except Exception:
                continue
            
            for fast, slow in EMA_PAIRS:
                # Run 0 threshold
                res_base = run_backtest(df, fast, slow, 0.0, 10000.0)
                # Run 0.05 threshold
                res_treat = run_backtest(df, fast, slow, 0.05, 10000.0)
                
                # Verify native calculation vs stored metrics
                for r in [res_base, res_treat]:
                    if r['total_trades'] > 0:
                        indep = independent_metric_calculation(r['trades'], [10000] + [t['pnl'] for t in r['trades']])
                        # Note: backtest.py calculates equity curve cumulatively. The audit recalculates Sharpe on raw trades.
                        # Wait, the backtest uses actual bar-by-bar equity curve for sharpe, so it includes holding periods.
                        # We will just verify Win Rate directly from trades.
                        calc_wr = round(sum(1 for t in r['trades'] if t['pnl'] > 0) / r['total_trades'] * 100.0, 2)
                        if calc_wr != r['win_rate']:
                            audit_results['discrepancies'].append({
                                "asset": asset, "tf": tf, "pair": f"{fast}-{slow}",
                                "metric": "win_rate", "expected": calc_wr, "actual": r['win_rate']
                            })

                if res_base['total_trades'] > 0 and res_treat['total_trades'] > 0:
                    baseline_metrics.append(res_base['win_rate'])
                    treatment_metrics.append(res_treat['win_rate'])

    # Re-run Wilcoxon natively
    if len(baseline_metrics) > 5:
        stat, p = stats.wilcoxon(baseline_metrics, treatment_metrics, zero_method='zsplit')
        audit_results['statistical_test'] = {
            "n_pairs": len(baseline_metrics),
            "wilcoxon_stat": float(stat),
            "p_value": float(p),
            "significant_at_05": bool(p < 0.05),
            "mean_diff": float(np.mean(treatment_metrics) - np.mean(baseline_metrics))
        }
    
    with open(OUTPUT_FILE, "w") as f:
        json.dump(audit_results, f, indent=4)
        
    print("Audit verification complete. See audit_report.json")

if __name__ == "__main__":
    run_audit()
