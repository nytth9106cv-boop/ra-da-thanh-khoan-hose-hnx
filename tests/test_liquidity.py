import numpy as np
import pandas as pd
import pytest

from src.finance.liquidity import amihud, days_to_liquidate, volume_zscore


def test_amihud_simple():
    close = pd.Series([100, 110, 110])
    value = pd.Series([1e9, 1e9, 1e9])
    result = amihud(close, value, window=2)
    assert np.isnan(result.iloc[1])
    assert result.iloc[2] == pytest.approx(0.05)


def test_days_to_liquidate():
    adv = pd.Series([50e9])
    result = days_to_liquidate(10e9, adv, participation=0.2)
    assert result.iloc[0] == pytest.approx(1.0)


def test_volume_zscore():
    vol = pd.Series([10, 20] * 30 + [30], dtype=float)
    z = volume_zscore(vol, window=60)
    expected = (30 - 15) / vol.iloc[:60].std()
    assert z.iloc[-1] == pytest.approx(expected)


def test_amihud_min_periods():
    close = pd.Series([100, 101, 101, 102, 102, 103, 103, 104, 104, 105, 105, 106], dtype=float)
    value = pd.Series([1e9, 1e9, 0, 1e9, 0, 1e9, 0, 1e9, 0, 1e9, 0, 1e9])
    assert pd.notna(amihud(close, value, window=12, min_periods=5).iloc[-1])
    assert pd.isna(amihud(close, value, window=12).iloc[-1])  # chỉ 6 ngày hợp lệ < 10