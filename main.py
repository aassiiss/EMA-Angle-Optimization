"""
main.py — Academic Execution Pipeline for EMA Angle Optimization (Phase 11).

This is the singular entry point for the backtesting framework. 
It orchestrates data acquisition, walk-forward parameter optimization, empirical analysis,
and publication-quality reporting.
"""

from src.reporting import generate_experiment_metadata
# We will skip old generate_all_charts for now, we will add new matplotlib generators later if needed
from src.optimizer import run_walk_forward_analysis, build_wfa_ranking_table, build_baseline_comparison_table
from src.statistical_tests import run_statistical_suite
from src.data_loader import download_data
from src.config import ensure_directories, TOTAL_COMBOS
import sys
import logging
import pandas as pd
from pathlib import Path

# Ensure stdout handles UTF-8 for console output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Configure logging before importing local modules to capture all logs
log_dir = Path("results/logs")
log_dir.mkdir(parents=True, exist_ok=True)
csv_dir = Path("results/csvs")
csv_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "run.log", encoding="utf-8", mode="w"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)


def export_csvs(wfa_results, baseline_results, regime_results, stat_df):
    log.info("  -> Exporting Walk-Forward Results to CSV...")
    wfa_df = build_wfa_ranking_table(wfa_results)
    wfa_df.to_csv(csv_dir / "walk_forward_results.csv", index=False)
    
    log.info("  -> Exporting Baseline Comparisons to CSV...")
    base_df = build_baseline_comparison_table(baseline_results)
    base_df.to_csv(csv_dir / "baseline_results.csv", index=False)
    
    log.info("  -> Exporting Statistical Tests to CSV...")
    if not stat_df.empty:
        stat_df.to_csv(csv_dir / "statistical_tests.csv", index=False)
        
    log.info("  -> Exporting Regime Robustness to CSV...")
    # Quick regime DF
    rows = []
    for asset, tf_dict in regime_results.items():
        for tf, data in tf_dict.items():
            m = data["metrics"]
            rows.append({
                "Asset": asset, "Timeframe": tf, "Regime": data["regime"],
                "Net Profit": m.get("total_net_profit", 0.0),
                "Sharpe": m.get("sharpe_ratio", 0.0)
            })
    reg_df = pd.DataFrame(rows)
    if not reg_df.empty:
        reg_df.to_csv(csv_dir / "regime_results.csv", index=False)


def main() -> None:
    """Executes the complete end-to-end academic backtesting pipeline."""

    log.info("=" * 70)
    log.info("  EMA Angle Strategy — Empirical Hardening (Phase 11)")
    log.info("=" * 70)

    # Pre-execution environment setup
    ensure_directories()
    generate_experiment_metadata()

    # 1. Data Acquisition
    log.info("\n[Phase 1] Acquiring Historical Market Data...")
    data_store = download_data()

    # 2. Walk-Forward Analysis (IS/OOS)
    log.info("\n[Phase 2] Executing Walk-Forward Optimization Engine...")
    results = run_walk_forward_analysis(data_store)
    
    wfa_results = results["wfa"]
    baseline_results = results["baselines"]
    regime_results = results["regimes"]

    # 3. Statistical Suite
    log.info("\n[Phase 3] Running Non-Parametric Statistical Suite...")
    stat_df = run_statistical_suite(baseline_results, wfa_results)

    # 4. CSV Reporting
    log.info("\n[Phase 4] Generating CSV Artifacts...")
    export_csvs(wfa_results, baseline_results, regime_results, stat_df)

    log.info("\n" + "=" * 70)
    log.info("  EMPIRICAL EXECUTION COMPLETE")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
