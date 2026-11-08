"""指标口径纯函数：输入聚合标量，输出派生指标。

口径唯一出处（docs/architecture.md 指标口径表）：
营收 = sum(order_item.amount)；客单价 = 营收 / 订单数；
毛利率 = (收入 - 成本) / 收入；浪费率 = 浪费量 / 备餐量；满意度 = 评分均值。
"""


def compute_kpis(revenue: float, order_count: int, cost_total: float,
                 prepared: int, wasted: int,
                 rating_sum: float, rating_count: int) -> dict:
    return {
        "revenue": round(revenue, 2),
        "orders": order_count,
        "avg_value": round(revenue / order_count, 2) if order_count else 0.0,
        "gross_margin": round((revenue - cost_total) / revenue, 4) if revenue else 0.0,
        "waste_rate": round(wasted / prepared, 4) if prepared else 0.0,
        "satisfaction": round(rating_sum / rating_count, 2) if rating_count else None,
    }


def with_delta(current: dict, previous: dict) -> dict:
    """逐指标挂环比：delta 为相对变化，基期为 0 或缺失记 None。"""
    result = {}
    for key, value in current.items():
        prev = previous.get(key)
        if value is None or prev in (None, 0):
            delta = None
        else:
            delta = round((value - prev) / prev, 4)
        result[key] = {"value": value, "prev": prev, "delta": delta}
    return result