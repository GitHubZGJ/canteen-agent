"""指标口径手算夹具验证。"""
from app.analytics.metrics import compute_kpis, with_delta


def test_compute_kpis_hand_calculated():
    # 营收 1000，订单 50，成本 600 → 客单价 20，毛利率 0.4
    # 备餐 200 浪费 30 → 浪费率 0.15；评分 (5+4+3)/3 = 4.0
    kpis = compute_kpis(revenue=1000.0, order_count=50, cost_total=600.0,
                        prepared=200, wasted=30, rating_sum=12.0, rating_count=3)
    assert kpis == {"revenue": 1000.0, "orders": 50, "avg_value": 20.0,
                    "gross_margin": 0.4, "waste_rate": 0.15, "satisfaction": 4.0}


def test_compute_kpis_empty():
    kpis = compute_kpis(0, 0, 0, 0, 0, 0, 0)
    assert kpis["avg_value"] == 0.0
    assert kpis["gross_margin"] == 0.0
    assert kpis["satisfaction"] is None


def test_with_delta():
    cur = {"revenue": 120.0, "orders": 0, "satisfaction": None}
    prev = {"revenue": 100.0, "orders": 5, "satisfaction": 4.0}
    out = with_delta(cur, prev)
    assert out["revenue"]["delta"] == 0.2
    assert out["orders"]["delta"] == -1.0      # 本期 0 基期 5 → -100%
    assert out["satisfaction"]["delta"] is None  # 本期缺失记 None


def test_with_delta_zero_base():
    out = with_delta({"revenue": 100.0}, {"revenue": 0})
    assert out["revenue"]["delta"] is None