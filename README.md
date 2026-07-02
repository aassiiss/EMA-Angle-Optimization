# EMA Angle Backtesting Engine (Academic Release)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Status](https://img.shields.io/badge/Status-Publication_Ready-success.svg)]()

This repository contains the source code for the quantitative backtesting framework used to evaluate **Exponential Moving Average (EMA) Angle Thresholds**. The project demonstrates that calculating the geometric vector (angle) of moving averages significantly improves the accuracy of trend-following strategies across various asset classes by filtering out horizontal, consolidating markets.

## Project Overview

Standard EMA crossovers suffer from severe "whipsawing" during periods of market consolidation. By calculating the arctangent of the EMA differential, this engine converts price momentum into a measurable degree angle ($\theta = \arctan(EMA_t - EMA_{t-1})$). 

The strategy requires a dual-filter confirmation:
1. Directional alignment of a Fast and Slow EMA.
2. The Fast EMA angle must exceed a specific mathematical threshold.
3. The Slow EMA angle must confirm the macro trend direction.

By evaluating 1,440 unique combinations of Assets, Timeframes, EMA Pairs, and Angle Thresholds, this framework empirically proves that steep angle requirements drastically reduce trade frequency while maximizing the probability of identifying a high-velocity trend.

## Repository Structure

```text
EMA_Angle_Optimization/
│
├── README.md               # Project overview and instructions
├── LICENSE                 # MIT License
├── requirements.txt        # Python dependency list
├── CITATION.cff            # Academic citation format
├── VERSION                 # Software versioning
│
├── config/
│   └── config.yaml         # Central configuration for all parameters
│
├── src/                    # Core Analytical Source Code
│   ├── indicators.py       # Mathematical EMA and vector angle logic
│   ├── strategy.py         # Signal generation logic
│   ├── backtest.py         # O(1) vectorized execution engine
│   ├── optimizer.py        # Grid search and combination sweeping
│   ├── visualization.py    # Publication-quality figure generation (300 DPI)
│   ├── export_excel.py     # Academic formatting for Excel results
│   ├── data_loader.py      # Historical OHLCV fetching via Yahoo Finance
│   └── reporting.py        # Metadata and Summary generation
│
├── tests/                  # Automated pytest Suite
│   └── test_core.py        # Validation of indicator math and execution logic
│
├── data/                   # Data Storage
│   └── raw/                # Cached OHLCV historical CSV files
│
├── results/                # Output Artifacts (Generated at runtime)
│   ├── excel/              # Detailed performance metrics per parameter set
│   ├── figures/            # Equity curves and trade execution plots
│   └── logs/               # Execution logs and environment metadata
│
└── main.py                 # The singular entry point pipeline
```

## Installation and Setup

This framework is built strictly with open-source dependencies.

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/EMA_Angle_Optimization.git
cd EMA_Angle_Optimization
```

### 2. Create a Virtual Environment (Optional but Recommended)
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

## How to Reproduce the Experiments

This repository is designed for full reproducibility. All execution logic is entirely deterministic (zero look-ahead bias, fixed T+1 execution logic).

To run the full 1,440 combination backtest grid:

```bash
python main.py
```

### What to Expect:
1. **Data Acquisition:** The engine will download historical tick data for Gold (GC=F), Silver (SI=F), and Bitcoin (BTC-USD) and cache it in `data/raw/`.
2. **Execution:** The backtest engine evaluates every parameter defined in `config/config.yaml`.
3. **Outputs:** The engine populates the `results/` directory with empirical data, high-resolution figures, and an execution log.

## Outputs Generated

Upon completion, you will find the following artifacts:
- `results/excel/EMA_Angle_Empirical_Results.xlsx`: The raw statistical breakdown, heavily filtered to highlight statistically significant combinations (Win Rate >= 50%).
- `results/figures/*.png`: 300 DPI charts showing Equity Curves and Price Execution trajectories for the highest-performing configurations.
- `results/logs/experiment_metadata.json`: A detailed capture of your operating system, Python environment, and exact parameter sets to guarantee peer reproducibility.
- `paper/Summary_of_Findings.md`: A formal writeup detailing the methodology, execution, and statistical findings of the run.

## Modifying Parameters

To evaluate new assets, alter starting capital, or expand the Angle thresholds, open `config/config.yaml` and modify the values directly. The engine dynamically maps to this file.

```yaml
# Example snippet from config.yaml
strategy:
  base_ema_values: [9, 15, 21, 50, 200]
  angle_thresholds: [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]

backtest:
  initial_equity: 10000.0
```

## Automated Testing

To verify the mathematical integrity of the geometric vectors and signal generation logic before running the full pipeline, execute the test suite:

```bash
pytest tests/
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Citation

If you utilize this backtesting engine or the geometric angle methodology in your academic research, please cite this repository using the provided `CITATION.cff` file.
