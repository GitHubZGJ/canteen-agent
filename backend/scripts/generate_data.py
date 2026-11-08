"""模拟数据生成器：产出食堂经营全量模拟数据，固定种子可复现。

用法（在 backend 目录下）：
    .venv/Scripts/python.exe scripts/generate_data.py            # 首次生成
    .venv/Scripts/python.exe scripts/generate_data.py --reset    # 清空经营数据后重建

数据全部为模拟，不含任何真实个人信息；日期范围默认 2026-05-11 ～ 2026-11-06。
"""
import argparse
import math
import random
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, insert
from sqlalchemy.orm import Session

from app.models import Canteen, Dish, Order, OrderItem, Review, Stall, WasteRecord

# 8 个档口 × 15 个菜品 = 120 个菜品；括号内为品类与价格区间
STALL_DEFS = [
    ("川湘风味", "热菜", (8, 18), ["宫保鸡丁", "麻婆豆腐", "回锅肉", "鱼香肉丝", "辣子鸡", "水煮肉片", "干煸豆角", "小炒黄牛肉", "剁椒鱼头", "酸辣土豆丝", "青椒肉丝", "红烧茄子", "蒜蓉西兰花", "番茄炒蛋", "孜然羊肉"]),
    ("粤式烧腊", "烧腊", (12, 22), ["烧鸭饭", "叉烧饭", "白切鸡", "豉油鸡", "烧鹅饭", "蜜汁排骨", "卤水拼盘", "盐焗鸡", "烧肉饭", "腊味煲仔饭", "蚝油牛肉", "清蒸鲈鱼", "上汤娃娃菜", "虾饺", "干炒牛河"]),
    ("面食档", "面食", (6, 15), ["兰州拉面", "牛肉刀削面", "炸酱面", "打卤面", "重庆小面", "热干面", "臊子面", "油泼面", "三鲜伊面", "鸡丝凉面", "牛肉米线", "酸辣粉", "羊肉泡馍", "馄饨面", "葱油拌面"]),
    ("轻食沙拉", "轻食", (10, 20), ["鸡胸肉沙拉", "牛油果沙拉", "藜麦碗", "三明治", "全麦卷饼", "水果捞", "酸奶杯", "蔬菜沙拉", "金枪鱼沙拉", "牛肉能量碗", "荞麦面沙拉", "鹰嘴豆泥卷", "烤蔬菜碗", "低卡便当", "燕麦杯"]),
    ("家常套餐", "套餐", (8, 16), ["红烧肉套餐", "糖醋里脊套餐", "可乐鸡翅套餐", "土豆炖牛腩套餐", "肉末粉丝套餐", "清炒时蔬套餐", "干锅花菜套餐", "香菇滑鸡套餐", "啤酒鸭套餐", "萝卜排骨汤套餐", "宫保虾球套餐", "地三鲜套餐", "木须肉套餐", "酱爆鸡丁套餐", "蒜苔炒肉套餐"]),
    ("铁板烧汁", "铁板", (10, 20), ["铁板豆腐", "铁板牛肉", "黑椒鸡排", "照烧鸡腿", "铁板鱿鱼", "香煎巴沙鱼", "铁板茄子", "芝士焗饭", "咖喱鸡饭", "黑椒牛柳意面", "日式蛋包饭", "韩式拌饭", "铁板虾", "蘑菇烩饭", "烤鸡腿饭"]),
    ("粥粉面点", "粥点", (3, 12), ["皮蛋瘦肉粥", "南瓜粥", "小米粥", "牛肉肠粉", "鲜虾云吞", "小笼包", "煎饺", "锅贴", "豆浆油条套餐", "茶叶蛋", "玉米棒", "蒸红薯", "烧麦", "糯米鸡", "红豆沙"]),
    ("麻辣香锅", "香锅", (12, 25), ["招牌香锅", "麻辣香锅荤", "素菜香锅", "番茄锅底", "菌菇锅底", "冒菜", "麻辣烫", "串串香", "酸辣拌", "麻辣拌", "干锅虾", "干锅排骨", "干锅土豆片", "冒鸭血", "宽粉套餐"]),
]
CANTEEN_DEFS = [("第一食堂", "校区东侧"), ("第二食堂", "校区西侧")]

SLOT_RANGES = {"breakfast": (7, 9), "lunch": (11, 13), "dinner": (17, 19)}
REVIEW_TEMPLATES = {
    5: ["味道很好，分量足，下次还来", "性价比很高，推荐", "出餐快，味道稳定"],
    4: ["整体不错，稍微有点咸", "味道可以，分量再大点就好了", "环境干净，口味在线"],
    3: ["中规中矩，能吃饱", "一般般，没什么记忆点", "价格还行，口味普通"],
    2: ["口味一般，等得有点久", "有点油，不太合口味", "分量偏少，性价比低"],
    1: ["不太新鲜，体验不好", "太咸了，没法吃完", "上菜太慢，态度一般"],
}
TAGS_BY_SENTIMENT = {
    "pos": ["口味好", "分量足", "性价比高", "出餐快"],
    "neu": ["一般", "还行", "能吃饱"],
    "neg": ["太咸", "太油", "上菜慢", "不新鲜", "分量少"],
}


def _day_factor(d: date, rng: random.Random) -> float:
    """客流日因子：工作日/周末、暑假、考试周、国庆、随机扰动。"""
    base = 2200 if d.weekday() < 5 else 1100
    factor = 1.0
    if d.month in (7, 8):
        factor *= 0.35  # 暑假留校人少
    if d.month == 6 and 22 <= d.day <= 28:
        factor *= 1.15  # 期末周
    if d.month == 10 and d.day <= 7:
        factor *= 0.4  # 国庆假期
    return base * factor * rng.uniform(0.9, 1.1)


def _nutrition(category: str, rng: random.Random) -> dict:
    light = category == "轻食"
    return {
        "calories": rng.randint(250, 450) if light else rng.randint(350, 850),
        "protein_g": rng.randint(20, 40) if light else rng.randint(10, 35),
        "fat_g": rng.randint(5, 15) if light else rng.randint(15, 45),
        "carbs_g": rng.randint(20, 45) if light else rng.randint(30, 90),
        "note": "按食材估算的模拟值",
    }


def reset_business_data(db: Session) -> None:
    """按外键依赖顺序清空经营数据（保留用户）。"""
    for model in (Review, OrderItem, WasteRecord, Order, Dish, Stall, Canteen):
        db.execute(delete(model))
    db.commit()


def generate(db: Session, days: int = 180, seed: int = 42,
             end_date: date = date(2026, 11, 6)) -> dict:
    """生成全量模拟数据，返回各表行数。同参数同种子结果完全一致。"""
    rng = random.Random(seed)
    start_date = end_date - timedelta(days=days - 1)

    # ---- 主数据：2 食堂、8 档口、120 菜品 ----
    canteen_rows = [{"id": i + 1, "name": n, "location": loc}
                    for i, (n, loc) in enumerate(CANTEEN_DEFS)]
    db.execute(insert(Canteen), canteen_rows)

    stall_rows, dish_rows = [], []
    dishes_by_stall: dict[int, list[dict]] = defaultdict(list)
    stall_weights: dict[int, list[float]] = {}
    dish_quality: dict[int, float] = {}
    for si, (name, category, price_range, names) in enumerate(STALL_DEFS):
        stall_id = si + 1
        stall_rows.append({"id": stall_id, "canteen_id": si // 4 + 1,
                           "name": name, "category": category})
        weights = []
        for di, dish_name in enumerate(names):
            dish_id = si * 15 + di + 1
            price = round(rng.uniform(*price_range) * 2) / 2
            pop = rng.lognormvariate(0, 0.6)
            if di == 14:
                pop *= 0.08  # 每档口一个滞销菜，保证预警功能在演示数据中可见
            row = {
                "id": dish_id, "stall_id": stall_id, "name": dish_name,
                "category": category, "price": price,
                "cost": round(price * rng.uniform(0.35, 0.6), 2),
                "tags": [category] + (["辣"] if category in ("热菜", "香锅", "面食") else ["清淡"]),
                "status": "on_sale", "nutrition_json": _nutrition(category, rng),
            }
            dish_rows.append(row)
            dishes_by_stall[stall_id].append(row)
            weights.append(pop)
            dish_quality[dish_id] = rng.uniform(0.55, 0.98)
        stall_weights[stall_id] = weights
    db.execute(insert(Stall), stall_rows)
    db.execute(insert(Dish), dish_rows)
    db.commit()

    stall_ids = list(stall_weights)
    stall_pop = [sum(w) for w in stall_weights.values()]

    # ---- 经营事实：订单、明细、评价 ----
    order_rows, item_rows, review_rows = [], [], []
    sold: dict[tuple[int, date], int] = defaultdict(int)
    day_orders: dict[date, int] = {}
    order_id = item_id = review_id = 0
    t0 = time.time()

    for day_offset in range(days):
        d = start_date + timedelta(days=day_offset)
        n_orders = int(_day_factor(d, rng))
        day_orders[d] = n_orders
        for seq in range(n_orders):
            order_id += 1
            stall_id = rng.choices(stall_ids, weights=stall_pop)[0]
            category = next(s["category"] for s in stall_rows if s["id"] == stall_id)
            slot_w = [0.4, 0.35, 0.25] if category == "粥点" else [0.12, 0.52, 0.36]
            slot = rng.choices(list(SLOT_RANGES), weights=slot_w)[0]
            h0, h1 = SLOT_RANGES[slot]
            dining_time = datetime(d.year, d.month, d.day,
                                   rng.randint(h0, h1 - 1), rng.randint(0, 59))
            k = 1 + (rng.random() < 0.45) + (rng.random() < 0.15)
            stall_dishes = dishes_by_stall[stall_id]
            chosen_idx = []
            while len(chosen_idx) < k:
                idx = rng.choices(range(len(stall_dishes)),
                                  weights=stall_weights[stall_id])[0]
                if idx not in chosen_idx:
                    chosen_idx.append(idx)
            amount = 0.0
            first_dish = None
            for idx in chosen_idx:
                dish = stall_dishes[idx]
                qty = 2 if rng.random() < 0.15 else 1
                item_id += 1
                line_amount = round(float(dish["price"]) * qty, 2)
                amount += line_amount
                item_rows.append({"id": item_id, "order_id": order_id,
                                  "dish_id": dish["id"], "quantity": qty,
                                  "price": dish["price"], "amount": line_amount})
                sold[(dish["id"], d)] += qty
                first_dish = first_dish or dish["id"]
            order_rows.append({
                "id": order_id, "order_no": f"MO{d:%Y%m%d}{seq:06d}",
                "canteen_id": stall_rows[stall_id - 1]["canteen_id"],
                "stall_id": stall_id,
                "channel": "takeout" if rng.random() < 0.15 else "dine_in",
                "dining_time": dining_time, "amount": round(amount, 2),
                "people_count": min(3, 1 + (k >= 2) + (rng.random() < 0.2)),
            })
            if rng.random() < 0.08:
                review_id += 1
                quality = dish_quality[first_dish]
                rating = max(1, min(5, round(quality * 5 + rng.gauss(0, 0.8))))
                sentiment = "pos" if rating >= 4 else "neu" if rating == 3 else "neg"
                review_rows.append({
                    "id": review_id, "order_id": order_id, "dish_id": first_dish,
                    "rating": rating, "content": rng.choice(REVIEW_TEMPLATES[rating]),
                    "tags": rng.sample(TAGS_BY_SENTIMENT[sentiment], 2),
                    "sentiment": sentiment, "created_at": dining_time,
                })
            if len(order_rows) >= 5000:
                db.execute(insert(Order), order_rows)
                db.execute(insert(OrderItem), item_rows)
                if review_rows:
                    db.execute(insert(Review), review_rows)
                db.commit()
                order_rows, item_rows, review_rows = [], [], []
        print(f"  {d} 订单 {n_orders}，累计 {order_id}，耗时 {time.time()-t0:.1f}s", flush=True)

    if order_rows:
        db.execute(insert(Order), order_rows)
        db.execute(insert(OrderItem), item_rows)
        if review_rows:
            db.execute(insert(Review), review_rows)
        db.commit()

    # ---- 浪费记录：每菜品每天一条 ----
    # 期望销量按全局权重占比：档口被选中概率 × 档口内菜品概率 = 菜品权重 / 全部权重
    grand_total = sum(sum(w) for w in stall_weights.values())
    waste_rows = []
    waste_id = 0
    for stall_id, dishes in dishes_by_stall.items():
        for dish in dishes:
            share = stall_weights[stall_id][dish["id"] - (stall_id - 1) * 15 - 1] / grand_total
            for d, n_orders in day_orders.items():
                waste_id += 1
                s = sold.get((dish["id"], d), 0)
                expected = n_orders * 1.84 * share  # 每单期望 1.6 个明细 × 1.15 平均份数
                if s == 0:
                    prepared = math.ceil(expected * rng.uniform(0.3, 0.6))
                    reason = "滞销备餐"
                else:
                    # 低质量菜品备餐冗余更高，浪费预警据此分化
                    quality = dish_quality[dish["id"]]
                    factor = rng.uniform(1.0, 1.1) + (1 - quality) * 0.25
                    prepared = math.ceil(max(s, expected * 0.6) * factor)
                    reason = "备餐过量" if prepared - s > s * 0.2 else "正常损耗"
                waste_rows.append({"id": waste_id, "stall_id": stall_id,
                                   "dish_id": dish["id"], "date": d,
                                   "prepared_qty": prepared, "sold_qty": s,
                                   "wasted_qty": prepared - s, "waste_reason": reason})
    db.execute(insert(WasteRecord), waste_rows)
    db.commit()

    return {"canteen": len(canteen_rows), "stall": len(stall_rows),
            "dish": len(dish_rows), "orders": order_id, "order_item": item_id,
            "review": review_id, "waste_record": waste_id,
            "start": str(start_date), "end": str(end_date)}


def main() -> None:
    parser = argparse.ArgumentParser(description="生成食堂经营模拟数据")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--end-date", type=lambda s: date.fromisoformat(s),
                        default=date(2026, 11, 6))
    parser.add_argument("--reset", action="store_true", help="清空已有经营数据后重建")
    args = parser.parse_args()

    from app.core.database import Base, SessionLocal, engine
    Base.metadata.create_all(engine)  # 脚本独立运行时保证表存在

    with SessionLocal() as db:
        existing = db.query(Canteen).count()
        if existing and not args.reset:
            print("已存在经营数据；如需重建请加 --reset")
            sys.exit(1)
        if args.reset:
            reset_business_data(db)
            print("已清空经营数据")
        counts = generate(db, days=args.days, seed=args.seed, end_date=args.end_date)
    print("生成完成：", counts)


if __name__ == "__main__":
    main()