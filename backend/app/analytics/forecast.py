"""备餐量预测纯函数：季节朴素基线、Holt-Winters、误差指标、预测区间。

序列以日期（pd.Timestamp）为索引、日销量为值，缺失日补 0。
季节周期取 7（周季节）；Holt-Winters 用加法趋势 + 加法季节、启发式初始化。
"""
import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

SEASONAL_PERIODS = 7
MIN_TRAIN_DAYS = 28   # 训练期有效（销量>0）天数下限
MIN_TRAIN_QTY = 50    # 训练期总销量下限


def seasonal_naive(series: pd.Series, test_dates: list) -> np.ndarray:
    """基线：预测值 = 上周同日实际值。"""
    preds = []
    for d in test_dates:
        prior = d - pd.Timedelta(days=SEASONAL_PERIODS)
        preds.append(float(series.get(prior, 0.0)))
    return np.array(preds, dtype=float)


def holt_winters(train: pd.Series, horizon: int) -> np.ndarray:
    """Holt-Winters 三次指数平滑预测，负值截断到 0；拟合失败由调用方兜底。"""
    model = ExponentialSmoothing(
        train.to_numpy(dtype=float),
        trend="add",
        seasonal="add",
        seasonal_periods=SEASONAL_PERIODS,
        initialization_method="heuristic",
    ).fit()
    return np.clip(model.forecast(horizon), 0, None)


def error_metrics(actual, pred) -> dict:
    """MAE 全量；MAPE 仅对实际值 > 0 的点计算（避免除零）。"""
    actual = np.asarray(actual, dtype=float)
    pred = np.asarray(pred, dtype=float)
    err = np.abs(actual - pred)
    mae = float(err.mean()) if len(err) else 0.0
    mask = actual > 0
    mape = float((err[mask] / actual[mask]).mean()) if mask.any() else None
    return {"mae": round(mae, 3), "mape": round(mape, 4) if mape is not None else None}


def prediction_band(pred, residual_std: float) -> tuple[np.ndarray, np.ndarray]:
    """±1.96σ 预测区间，下界截断到 0。"""
    pred = np.asarray(pred, dtype=float)
    half = 1.96 * float(residual_std)
    return np.clip(pred - half, 0, None), pred + half


def is_sufficient(train: pd.Series) -> bool:
    return int((train > 0).sum()) >= MIN_TRAIN_DAYS and float(train.sum()) >= MIN_TRAIN_QTY