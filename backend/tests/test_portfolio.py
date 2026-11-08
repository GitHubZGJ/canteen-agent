"""四象限、ABC、滞销的手算夹具验证。"""
import pandas as pd

from app.analytics.portfolio import add_abc, add_quadrant, find_slow_movers


def test_quadrant_hand_calculated():
    # 销量中位数 15，毛利率中位数 0.45
    df = pd.DataFrame({
        "dish_id": [1, 2, 3, 4],
        "quantity": [20, 10, 20, 10],
        "margin_rate": [0.5, 0.5, 0.4, 0.4],
    })
    out, thresholds = add_quadrant(df)
    assert thresholds == {"qty_median": 15.0, "margin_median": 0.45}
    assert out.set_index("dish_id")["quadrant"].to_dict() == {
        1: "明星", 2: "金牛", 3: "问题", 4: "瘦狗",
    }


def test_quadrant_median_boundary_is_high():
    # 等于中位数判高侧：两菜品值相同则双高 → 明星
    df = pd.DataFrame({"quantity": [10, 10], "margin_rate": [0.5, 0.5]})
    out, _ = add_quadrant(df)
    assert (out["quadrant"] == "明星").all()


def test_abc_cumulative_boundary():
    # 营收 60/25/10/5：A 累计到 60%（<70%）含第 2 个？60+25=85%
    # 第 1 个之前累计 0 → A；第 2 个之前 0.6 <0.7 → A；第 3 个之前 0.85 → B；第 4 个之前 0.95 → C
    df = pd.DataFrame({"dish_id": [1, 2, 3, 4], "revenue": [60.0, 25.0, 10.0, 5.0]})
    out = add_abc(df).set_index("dish_id")
    assert out["abc"].to_dict() == {1: "A", 2: "A", 3: "B", 4: "C"}


def test_abc_zero_revenue():
    df = pd.DataFrame({"dish_id": [1, 2], "revenue": [0.0, 0.0]})
    assert (add_abc(df)["abc"] == "C").all()


def test_slow_mover_needs_full_7_days():
    dates = pd.date_range("2026-11-01", periods=7).date
    # 档口均值每天 100，阈值 20；菜品 1 连续 7 天卖 10 → 滞销
    # 菜品 2 第 6 天卖 25（≥阈值）→ 不滞销；菜品 3 只有 6 天数据 → 不判定
    daily = pd.DataFrame(
        {d: [10, 10 if i != 5 else 25] for i, d in enumerate(dates)},
        index=[1, 2],
    )
    stall_avg = pd.Series(100.0, index=dates)
    assert find_slow_movers(daily, stall_avg) == [1]
    short = pd.DataFrame({d: [10] for d in dates[:6]}, index=[3])
    assert find_slow_movers(short, stall_avg) == []


def test_reviews_summary():
    from app.analytics.reviews import summarize_reviews, weighted_nutrition

    df = pd.DataFrame({
        "rating": [5, 3, 1],
        "sentiment": ["pos", "neu", "neg"],
        "tags": [["口味好", "分量足"], ["一般"], ["太咸"]],
    })
    out = summarize_reviews(df)
    assert out["count"] == 3
    assert out["avg_rating"] == 3.0
    assert out["rating_dist"] == {"1": 1, "3": 1, "5": 1}
    assert out["tag_counts"]["口味好"] == 1

    nut = pd.DataFrame({"quantity": [2, 1], "calories": [400, 700],
                        "protein_g": [20, 10], "fat_g": [10, 40], "carbs_g": [50, 80]})
    w = weighted_nutrition(nut)
    # (400*2+700)/3 = 500
    assert w["avg_calories"] == 500.0
    assert w["sold_qty"] == 3