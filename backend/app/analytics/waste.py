"""浪费预警纯函数：浪费率超阈值且备餐量达到下限的菜品进入预警。"""
import pandas as pd

ALERT_RATE = 0.15
ALERT_MIN_PREPARED = 50


def find_waste_alerts(df: pd.DataFrame) -> pd.DataFrame:
    """输入需含 dish_id、prepared、wasted 列；输出加 waste_rate 列的预警子集。"""
    out = df.copy()
    out["waste_rate"] = (out["wasted"] / out["prepared"].where(out["prepared"] > 0)).fillna(0.0)
    return out[(out["waste_rate"] > ALERT_RATE) & (out["prepared"] >= ALERT_MIN_PREPARED)]