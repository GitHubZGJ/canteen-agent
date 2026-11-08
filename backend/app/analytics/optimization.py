"""菜单多目标优化纯函数：营养均衡打分、归一化加权、保底与档口下限约束。

打分 = w_margin·毛利 + w_satisfaction·满意度 + w_nutrition·营养 + w_waste·(1-浪费率)，
各目标先 min-max 归一到 [0,1]；权重自动归一，允许用户只调相对比例。
动作：得分前 20% 推广，底部 20% 中非保底且满足档口下限者汰换，其余保留。
全程无随机，排序以 dish_id 决胜，结果完全可复现。
"""
import pandas as pd

DEFAULT_WEIGHTS = {"margin": 0.4, "satisfaction": 0.3, "nutrition": 0.15, "waste": 0.15}
MIN_KEEP_PER_STALL = 10
ACTION_QUANTILE = 0.2


def nutrition_score(nutrition: dict) -> float:
    """热量适中（400～700 满分）、蛋白充足（≥25g 满分）、脂肪适中（≤25g 满分）。"""
    cal = float(nutrition.get("calories", 600))
    protein = float(nutrition.get("protein_g", 15))
    fat = float(nutrition.get("fat_g", 30))
    cal_s = 1.0 if 400 <= cal <= 700 else max(0.0, 1 - abs(cal - 550) / 550)
    protein_s = min(1.0, protein / 25)
    fat_s = 1.0 if fat <= 25 else max(0.0, 1 - (fat - 25) / 40)
    return round((cal_s + protein_s + fat_s) / 3, 4)


def _minmax(s: pd.Series) -> pd.Series:
    lo, hi = float(s.min()), float(s.max())
    if hi == lo:
        return pd.Series(0.5, index=s.index)
    return (s - lo) / (hi - lo)


def score_dishes(df: pd.DataFrame, weights: dict | None = None) -> pd.DataFrame:
    """输入需含 margin_rate、avg_rating、nutrition_score、waste_rate、dish_id、stall_id。"""
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    total = sum(w.values())
    w = {k: v / total for k, v in w.items()}
    out = df.copy()
    rating = out["avg_rating"].fillna(out["avg_rating"].median())
    out["n_margin"] = _minmax(out["margin_rate"])
    out["n_satisfaction"] = _minmax(rating)
    out["n_nutrition"] = _minmax(out["nutrition_score"])
    out["n_waste"] = _minmax(1 - out["waste_rate"])
    out["score"] = (
        w["margin"] * out["n_margin"]
        + w["satisfaction"] * out["n_satisfaction"]
        + w["nutrition"] * out["n_nutrition"]
        + w["waste"] * out["n_waste"]
    ).round(4)
    return out


def assign_actions(scored: pd.DataFrame, protected: list[int] | None = None) -> pd.DataFrame:
    protected = set(protected or [])
    out = scored.sort_values(["score", "dish_id"], ascending=[False, True]).copy()
    n = len(out)
    top_n = max(1, int(n * ACTION_QUANTILE))
    bottom_n = max(1, int(n * ACTION_QUANTILE))
    out["action"] = "保留"
    out.iloc[:top_n, out.columns.get_loc("action")] = "推广"
    quota = {sid: max(0, len(g) - MIN_KEEP_PER_STALL) for sid, g in out.groupby("stall_id")}
    for idx in out.index[n - bottom_n:]:
        row = out.loc[idx]
        sid = row["stall_id"]
        if int(row["dish_id"]) in protected:
            continue
        if quota.get(sid, 0) > 0:
            out.at[idx, "action"] = "汰换"
            quota[sid] -= 1
    return out