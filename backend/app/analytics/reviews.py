"""评价与营养纯函数。"""
import pandas as pd


def summarize_reviews(df: pd.DataFrame) -> dict:
    """输入需含 rating、sentiment、tags 列。"""
    if df.empty:
        return {"count": 0, "avg_rating": None, "rating_dist": {},
                "sentiment_dist": {}, "tag_counts": {}}
    tag_counts: dict[str, int] = {}
    for tags in df["tags"]:
        for tag in tags or []:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    return {
        "count": len(df),
        "avg_rating": round(float(df["rating"].mean()), 2),
        "rating_dist": {str(k): int(v) for k, v in df["rating"].value_counts().sort_index().items()},
        "sentiment_dist": {k: int(v) for k, v in df["sentiment"].value_counts().items()},
        "tag_counts": dict(sorted(tag_counts.items(), key=lambda x: -x[1])),
    }


def weighted_nutrition(df: pd.DataFrame) -> dict:
    """输入需含 quantity、calories、protein_g、fat_g、carbs_g 列（按销量加权）。"""
    total_qty = int(df["quantity"].sum()) if len(df) else 0
    if total_qty == 0:
        return {"sold_qty": 0, "avg_calories": None, "avg_protein_g": None,
                "avg_fat_g": None, "avg_carbs_g": None}
    return {
        "sold_qty": total_qty,
        "avg_calories": round(float((df["calories"] * df["quantity"]).sum() / total_qty), 1),
        "avg_protein_g": round(float((df["protein_g"] * df["quantity"]).sum() / total_qty), 1),
        "avg_fat_g": round(float((df["fat_g"] * df["quantity"]).sum() / total_qty), 1),
        "avg_carbs_g": round(float((df["carbs_g"] * df["quantity"]).sum() / total_qty), 1),
    }