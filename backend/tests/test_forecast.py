"""预测纯函数：手算夹具 + 合成周季节序列验证 Holt-Winters 优于季节朴素基线。"""
import numpy as np
import pandas as pd

from app.analytics.forecast import (
    error_metrics,
    holt_winters,
    is_sufficient,
    prediction_band,
    seasonal_naive,
)


def test_seasonal_naive():
    dates = pd.date_range("2026-01-01", periods=21)
    series = pd.Series(range(21), index=dates, dtype=float)
    pred = seasonal_naive(series, list(dates[14:21]))
    # 测试期第 14～20 天，预测取 7～13 天值
    assert pred.tolist() == list(range(7, 14))


def test_error_metrics_hand():
    out = error_metrics([10, 20, 0], [12, 18, 5])
    assert out["mae"] == 3.0           # (2+2+5)/3
    assert out["mape"] == 0.15         # (2/10+2/20)/2，跳过实际为 0 的点


def test_error_metrics_all_zero():
    assert error_metrics([0, 0], [1, 2])["mape"] is None


def test_prediction_band():
    lower, upper = prediction_band([10, 1], 2.0)
    assert round(lower[0], 2) == 6.08  # 10-1.96*2
    assert round(upper[0], 2) == 13.92
    assert lower[1] == 0.0             # 1-3.92 截断到 0


def test_is_sufficient():
    dates = pd.date_range("2026-01-01", periods=40)
    assert is_sufficient(pd.Series(2.0, index=dates))
    assert not is_sufficient(pd.Series(0.0, index=dates))
    sparse = pd.Series(0.0, index=dates)
    sparse.iloc[:10] = 5.0
    assert not is_sufficient(sparse)   # 有效天数 10 < 28


def test_holt_winters_beats_naive_on_weekly_season():
    rng = np.random.default_rng(42)
    n = 120
    dates = pd.date_range("2026-01-01", periods=n)
    weekly = 20 * np.sin(2 * np.pi * np.arange(n) / 7)
    values = 100 + weekly + rng.normal(0, 3, n)
    series = pd.Series(values, index=dates)
    train, test = series.iloc[:106], series.iloc[106:]
    hw = holt_winters(train, 14)
    naive = seasonal_naive(series, list(test.index))
    assert len(hw) == 14
    assert (hw >= 0).all()
    hw_mae = error_metrics(test.to_numpy(), hw)["mae"]
    naive_mae = error_metrics(test.to_numpy(), naive)["mae"]
    assert hw_mae < naive_mae, f"HW {hw_mae} 应优于朴素 {naive_mae}"