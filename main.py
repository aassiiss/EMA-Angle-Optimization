"""
main.py — Academic Execution Pipeline for EMA Angle Optimization.

This is the singular entry point for the backtesting framework. 
It orchestrates data acquisition, parameter optimization, empirical analysis,
and publication-quality reporting.
"""

from src.reporting import generate_experiment_metadata, generate_summary_report
from src.visualization import generate_all_charts
from src.export_excel import ExcelExporter
from src.optimizer import run_full_sweep
from src.data_loader import download_data
from src.config import (
    ensure_directories, TOTAL_COMBOS, INITIAL_EQUITY,
    RESULT_EXCEL_DIR, RESULT_REPORTS_DIR
)
import sys
import logging
from pathlib import Path

# Ensure stdout handles UTF-8 for console output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Configure logging before importing local modules to capture all logs
log_dir = Path("results/logs")
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "run.log", encoding="utf-8", mode="w"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)

# Import local modules


def main() -> None:
    """Executes the complete end-to-end academic backtesting pipeline."""

    log.info("=" * 70)
    log.info("  EMA Angle Strategy Optimization — Academic Release Pipeline")
    log.info(f"  Total Parameter Combinations: {TOTAL_COMBOS}")
    log.info("=" * 70)

    # Pre-execution environment setup
    ensure_directories()
    generate_experiment_metadata()

    # 1. Data Acquisition
    log.info("\n[Phase 1] Acquiring Historical Market Data...")
    data_store = download_data()

    # 2. Optimization Sweep
    log.info("\n[Phase 2] Executing Vectorized Backtest Grid...")
    results = run_full_sweep(data_store, INITIAL_EQUITY)

    # 3. Academic Reporting & Exports
    log.info("\n[Phase 3] Generating Publication-Quality Outputs...")

    # 3.1 Excel Export
    excel_path = RESULT_EXCEL_DIR / "EMA_Angle_Empirical_Results.xlsx"
    ExcelExporter().export(results, INITIAL_EQUITY, excel_path)

    # 3.2 Figure Generation
    log.info("  -> Generating High-Resolution Charts (300 DPI)...")
    generate_all_charts(data_store, results)

    # 3.3 Text Summary
    report_path = RESULT_REPORTS_DIR / "Summary_of_Findings.md"
    generate_summary_report(results, report_path)

    # Also save a copy to the paper/ directory as requested
    paper_dir = Path("paper")
    paper_dir.mkdir(parents=True, exist_ok=True)
    generate_summary_report(results, paper_dir / "Summary_of_Findings.md")

    log.info("\n" + "=" * 70)
    log.info("  EXECUTION COMPLETE")
    log.info("  All outputs, metadata, and logs have been successfully generated.")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
