"""优化纯函数：营养打分、加权公式手算、约束与确定性。"""
import pandas as pd

from app.analytics.optimization import assign_actions, nutrition_score, score_dishes


def test_nutrition_score():
    assert nutrition_score({"calories": 550, "protein_g": 25, "fat_g": 20}) == 1.0
    low = nutrition_score({"calories": 1100, "protein_g": 5, "fat_g": 65})
    assert low < 0.3


def test_score_formula_hand():
    df = pd.DataFrame({
        "dish_id": [1, 2, 3], "stall_id": [1, 1, 1],
        "margin_rate": [0.2, 0.4, 0.6],
        "avg_rating": [3.0, 4.0, 5.0],
        "nutrition_score": [0.3, 0.6, 0.9],
        "waste_rate": [0.3, 0.2, 0.1],
    })
    out = score_dishes(df).set_index("dish_id")
    # 各目标 min-max 后均为 [0,0.5,1]，默认权重和为 1
    assert out.loc[1, "score"] == 0.0
    assert out.loc[2, "score"] == 0.5
    assert out.loc[3, "score"] == 1.0


def test_weights_change_scores():
    df = pd.DataFrame({
        "dish_id": [1, 2], "stall_id": [1, 1],
        "margin_rate": [0.6, 0.2], "avg_rating": [2.0, 5.0],
        "nutrition_score": [0.5, 0.5], "waste_rate": [0.1, 0.1],
    })
    margin_heavy = score_dishes(df, {"margin": 0.9, "satisfaction": 0.1}).set_index("dish_id")
    assert margin_heavy.loc[1, "score"] > margin_heavy.loc[2, "score"]
    satisfaction_heavy = score_dishes(df, {"margin": 0.1, "satisfaction": 0.9}).set_index("dish_id")
    assert satisfaction_heavy.loc[2, "score"] > satisfaction_heavy.loc[1, "score"]


def _fixture(n=24):
    return pd.DataFrame({
        "dish_id": list(range(1, n + 1)),
        "stall_id": [1 if i <= 12 else 2 for i in range(1, n + 1)],
        "score": [float(i) for i in range(1, n + 1)],
    })


def test_actions_constraints_and_protected():
    out = assign_actions(_fixture(), protected=[4]).set_index("dish_id")
    assert (out["action"] == "推广").sum() == 4        # 前 20%
    removed = out[out["action"] == "汰换"]
    assert len(removed) == 2                          # 档口 1 仅 12 个，下限 10 → 最多汰换 2
    assert 4 not in removed.index                     # 保底菜品不汰换
    assert (out.loc[out["stall_id"] == 1, "action"] != "汰换").sum() == 10  # 档口 1 保留 10


def test_deterministic():
    df = pd.DataFrame({
        "dish_id": [1, 2, 3], "stall_id": [1, 1, 1],
        "margin_rate": [0.5, 0.3, 0.4], "avg_rating": [4.0, 3.0, 5.0],
        "nutrition_score": [0.6, 0.5, 0.7], "waste_rate": [0.1, 0.2, 0.15],
    })
    a = assign_actions(score_dishes(df))
    b = assign_actions(score_dishes(df))
    pd.testing.assert_frame_equal(a, b)