"""菜品组合纯函数：四象限、ABC 分类、滞销判定。

四象限以销量中位数与毛利率中位数切分（双高为明星）；
ABC 按营收累计占比：累计达到 70% 之前为 A，达到 90% 之前为 B，其余为 C；
滞销：连续 7 天日销量低于所在档口当日菜品均值销量的 20%。
"""
import pandas as pd

QUADRANTS = ("明星", "金牛", "问题", "瘦狗")
SLOW_DAYS = 7
SLOW_RATIO = 0.2


def add_quadrant(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """输入需含 quantity、margin_rate 列；返回加了 quadrant 列的副本与阈值。"""
    qty_median = float(df["quantity"].median()) if len(df) else 0.0
    margin_median = float(df["margin_rate"].median()) if len(df) else 0.0

    def label(row) -> str:
        high_qty = row["quantity"] >= qty_median
        high_margin = row["margin_rate"] >= margin_median
        if high_qty and high_margin:
            return "明星"
        if high_margin:
            return "金牛"
        if high_qty:
            return "问题"
        return "瘦狗"

    out = df.copy()
    out["quadrant"] = out.apply(label, axis=1) if len(out) else pd.Series(dtype=str)
    return out, {"qty_median": qty_median, "margin_median": margin_median}


def add_abc(df: pd.DataFrame) -> pd.DataFrame:
    """输入需含 revenue 列；按营收降序累计占比切 A/B/C。"""
    out = df.sort_values("revenue", ascending=False).copy()
    total = out["revenue"].sum()
    if total <= 0:
        out["abc"] = "C"
        out["revenue_share"] = 0.0
        return out
    share = out["revenue"] / total
    cum_before = share.cumsum() - share  # 本菜品之前的累计占比
    out["revenue_share"] = share.round(4)
    out["abc"] = ["A" if c < 0.7 else "B" if c < 0.9 else "C" for c in cum_before]
    return out


def find_slow_movers(daily_qty: pd.DataFrame, stall_avg: pd.Series) -> list[int]:
    """daily_qty：index=dish_id，columns=日期，值=当日销量（缺失补 0）。

    stall_avg：index=日期，值=该档口当日菜品均值销量；调用方按档口分组传入。
    返回连续 SLOW_DAYS 天低于阈值 ratio 的菜品 id。
    """
    if daily_qty.empty or len(daily_qty.columns) < SLOW_DAYS:
        return []
    last_dates = list(daily_qty.columns[-SLOW_DAYS:])
    slow = []
    for dish_id, row in daily_qty.iterrows():
        if all(float(row[d]) < SLOW_RATIO * float(stall_avg[d]) for d in last_dates):
            slow.append(int(dish_id))
    return slow