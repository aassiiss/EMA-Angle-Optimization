import pytest
import numpy as np
import pandas as pd
from typing import Dict, Any

from src.indicators import calc_ema, calc_slope, calc_angle, add_ema_features
from src.strategy import generate_signals
from src.backtest import run_backtest

# ── Fixtures ─────────────────────────────────────────────────────────────
@pytest.fixture
def mock_price_data() -> pd.DataFrame:
    """Creates a deterministic dummy price series for testing."""
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    data = {
        "Open":   [100, 102, 104, 103, 101,  99,  98, 100, 105, 110],
        "High":   [101, 103, 105, 104, 102, 100,  99, 101, 106, 111],
        "Low":    [ 99, 101, 103, 102, 100,  98,  97,  99, 104, 109],
        "Close":  [100, 102, 104, 103, 101,  99,  98, 100, 105, 110],
        "Volume": [1000] * 10
    }
    return pd.DataFrame(data, index=dates)

# ── Mathematical Tests ───────────────────────────────────────────────────
def test_calc_ema(mock_price_data: pd.DataFrame):
    """Verifies the EMA calculation against deterministic bounds."""
    ema_3 = calc_ema(mock_price_data["Close"], 3)
    assert len(ema_3) == len(mock_price_data)
    assert not ema_3.isna().any()
    # First value should match first close
    assert ema_3.iloc[0] == 100.0

def test_calc_slope(mock_price_data: pd.DataFrame):
    """Verifies that the geometric slope represents nominal difference."""
    ema = calc_ema(mock_price_data["Close"], 3)
    slope = calc_slope(ema)
    # First slope is NaN
    assert pd.isna(slope.iloc[0])
    # Second slope = EMA_t - EMA_{t-1}
    expected_slope = ema.iloc[1] - ema.iloc[0]
    assert np.isclose(slope.iloc[1], expected_slope)

def test_calc_angle(mock_price_data: pd.DataFrame):
    """Verifies the arctangent conversion from slope to degree angle."""
    ema = calc_ema(mock_price_data["Close"], 3)
    angle = calc_angle(ema)
    assert pd.isna(angle.iloc[0])
    
    slope_val = ema.iloc[1] - ema.iloc[0]
    expected_angle = np.degrees(np.arctan(slope_val))
    assert np.isclose(angle.iloc[1], expected_angle)

def test_feature_augmentation(mock_price_data: pd.DataFrame):
    """Verifies that the OHLCV dataset is correctly augmented."""
    augmented = add_ema_features(mock_price_data, fast=3, slow=5)
    
    required_columns = [
        "ema_fast", "ema_slow", "slope_fast", 
        "slope_slow", "angle_fast", "angle_slow"
    ]
    for col in required_columns:
        assert col in augmented.columns

# ── Logic Tests ──────────────────────────────────────────────────────────
def test_generate_signals(mock_price_data: pd.DataFrame):
    """Verifies that signal generation respects the dual-filter conditions."""
    feat = add_ema_features(mock_price_data, fast=3, slow=5)
    
    # 0 degree threshold (pure crossover + slow momentum confirmation)
    sigs_0 = generate_signals(feat, threshold=0)
    assert len(sigs_0) == len(feat)
    
    # Extremely high threshold (should yield mostly 0 signals)
    sigs_90 = generate_signals(feat, threshold=89.9)
    assert (sigs_90 == 0).all()

# ── Execution Tests ──────────────────────────────────────────────────────
def test_run_backtest(mock_price_data: pd.DataFrame):
    """Verifies the core execution engine and metric generation."""
    metrics: Dict[str, Any] = run_backtest(
        df=mock_price_data, 
        fast=3, 
        slow=5, 
        threshold=0, 
        initial_equity=10000.0
    )
    
    assert "total_trades" in metrics
    assert "final_equity" in metrics
    assert metrics["fast_ema"] == 3
    assert metrics["slow_ema"] == 5
    assert metrics["angle_threshold"] == 0
    assert metrics["total_trades"] >= 0
