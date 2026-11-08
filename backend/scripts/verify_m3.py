"""M3 验收验证：真实数据回测达标、优化可复现、权限与约束。

核心验收：Holt-Winters 在同子集上优于季节朴素基线（MAE 与 MAPE 双双更低）。
退出码：0 全部通过；1 存在失败项。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.main import app

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append(cond)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"（{detail}）" if detail else ""))


def main() -> None:
    with TestClient(app) as client:
        admin = client.post("/api/auth/login",
                            json={"username": "admin", "password": "Admin@123"}).json()["data"]["token"]
        client.headers["Authorization"] = f"Bearer {admin}"

        # ---- 全量回测：120 菜品 × 3 时段 ----
        resp = client.post("/api/forecast/runs", json={"horizon": 14})
        assert resp.status_code == 200, resp.text
        run = resp.json()["data"]
        m = run["metrics"]
        hw, naive_sub = m["holt_winters"], m["seasonal_naive_same_subset"]
        check("Holt-Winters 参与对比的序列数 > 0", m["holt_winters_pairs"] > 0,
              f"pairs={m['holt_winters_pairs']}，回退 {run['fallback_count']} 个")
        check("同子集 MAE 优于季节朴素基线", hw["mae"] < naive_sub["mae"],
              f"HW {hw['mae']} < naive {naive_sub['mae']}")
        check("同子集 MAPE 优于季节朴素基线", hw["mape"] < naive_sub["mape"],
              f"HW {hw['mape']} < naive {naive_sub['mape']}")
        check("备餐节约测算为正", run["total_estimated_saving"] > 0,
              f"预计日节约 {run['total_estimated_saving']} 份")

        detail = client.get(f"/api/forecast/runs/{run['run_id']}").json()["data"]
        check("结果序列 = 全部菜品 × 3 时段", len(detail["series"]) == 120 * 3,
              f"{len(detail['series'])} 条")
        points = [p for s in detail["series"] for p in s["points"]]
        check("每条序列 14 天且含上下界与实际值",
              len(points) == 120 * 3 * 14
              and all(p["lower"] <= p["upper"] and p["actual"] >= 0 for p in points),
              f"{len(points)} 个点")

        # ---- 单菜品两次运行：算法确定性（同数据同结果） ----
        r1 = client.post("/api/forecast/runs", json={"dish_id": 1, "horizon": 14}).json()["data"]
        r2 = client.post("/api/forecast/runs", json={"dish_id": 1, "horizon": 14}).json()["data"]
        check("单菜品回测指标可复现",
              r1["metrics"]["holt_winters"] == r2["metrics"]["holt_winters"]
              and r1["metrics"]["chosen"] == r2["metrics"]["chosen"])
        s1 = client.get(f"/api/forecast/runs/{r1['run_id']}").json()["data"]["series"]
        s2 = client.get(f"/api/forecast/runs/{r2['run_id']}").json()["data"]["series"]
        check("预测序列逐点一致", s1 == s2)

        # ---- 菜单优化 ----
        o1 = client.post("/api/optimization/runs", json={}).json()["data"]
        o2 = client.post("/api/optimization/runs", json={}).json()["data"]
        check("优化结果固定输入可复现", o1["dishes"] == o2["dishes"])
        check("动作计数合计 120", sum(o1["counts"].values()) == 120, str(o1["counts"]))
        lowest = min(o1["dishes"], key=lambda d: d["score"])["dish_id"]
        o3 = client.post("/api/optimization/runs", json={"protected": [lowest]}).json()["data"]
        check("保底菜品不被汰换",
              next(d for d in o3["dishes"] if d["dish_id"] == lowest)["action"] != "汰换")
        check("默认权重下三类动作均出现",
              len([k for k, v in o1["counts"].items() if v > 0]) == 3, str(o1["counts"]))

        # ---- 权限与参数校验 ----
        viewer = client.post("/api/auth/login",
                             json={"username": "viewer", "password": "Viewer@123"}).json()["data"]["token"]
        rv = client.post("/api/forecast/runs", json={"dish_id": 1},
                         headers={"Authorization": f"Bearer {viewer}"})
        check("viewer 无法发起预测", rv.status_code == 403 and rv.json()["msg"] == "权限不足")
        bad = client.post("/api/forecast/runs", json={"horizon": 5})
        check("horizon 越界拒绝且 msg 明确",
              bad.status_code == 400 and bad.json()["code"] == 1001
              and "参数校验失败" in bad.json()["msg"])
        missing = client.get("/api/optimization/runs/99999")
        check("不存在优化运行 404", missing.status_code == 404
              and missing.json()["msg"] == "优化运行不存在")

    failed = RESULTS.count(False)
    print(f"\n合计 {len(RESULTS)} 项，失败 {failed} 项")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()