"""智能体编排器：规则规划器 + 大模型「计划-执行」循环，事件流输出。

事件：mode / tool_call / tool_result / fallback / message / done。
每次工具调用写 tool_call_log；助手消息在流结束前落库并带上 message_id。
"""
import json
import time
from collections.abc import Iterator
from datetime import date

from sqlalchemy.orm import Session

from app.agent.providers import build_provider
from app.core.config import settings
from app.core.exceptions import ERR_FORBIDDEN, BizException
from app.models import AgentMessage, AgentSession, ToolCallLog, User
from app.tools import execute_tool, openai_tools, summarize_result
from app.tools.registry import TOOLS

SYSTEM_PROMPT = """你是校园食堂经营分析助手，服务食堂经理。
规则：
1. 所有数字必须来自工具返回，严禁编造或估算。
2. 需要经营数据时先调用合适的工具；一次只回答用户当前的问题。
3. 你可以创建建议工单草稿（create_suggestion），但无权审批或执行；不得声称已生效。
4. 用简洁中文回答：先给结论，再给关键依据；涉及日期时说明统计区间。
5. 今天是 {today}，数据最新日期由工具返回的 range 指明。"""

RULE_INTENTS = [
    (("指标", "营收", "客流", "订单", "客单", "毛利", "生意", "经营情况"), "query_metrics"),
    (("四象限", "滞销", "组合", "abc", "ABC"), "analyze_portfolio"),
    (("预测", "备餐"), "forecast_demand"),
    (("优化", "菜单结构", "汰换", "推广"), "optimize_menu"),
    (("评价", "满意", "口碑", "差评"), "analyze_reviews"),
    (("浪费", "损耗", "预警"), "detect_waste"),
    (("周报", "报告"), "generate_report"),
]


class AgentEngine:
    def __init__(self, db: Session, session: AgentSession, user: User,
                 history: list[dict], provider=None):
        self.db = db
        self.session = session
        self.user = user
        self.history = history
        self.provider = provider if provider is not None else build_provider()
        self.assistant: AgentMessage | None = None
        self.tool_records: list[dict] = []

    def _start_assistant(self) -> AgentMessage:
        message = AgentMessage(session_id=self.session.id, role="assistant", content="")
        self.db.add(message)
        self.db.flush()
        self.assistant = message
        return message

    def _call_tool(self, name: str, args: dict) -> dict:
        started = time.perf_counter()
        try:
            spec = TOOLS.get(name)
            if spec is not None and spec.write and self.user.role not in ("admin", "manager"):
                raise BizException(ERR_FORBIDDEN, "当前角色无写操作权限")
            result = execute_tool(self.db, self.user, name, args)
            status = "ok"
        except BizException as exc:
            result = {"error": exc.msg}
            status = "error"
        latency = int((time.perf_counter() - started) * 1000)
        self.db.add(ToolCallLog(message_id=self.assistant.id, tool_name=name,
                                args_json=args or {},
                                result_summary=summarize_result(result),
                                status=status, latency_ms=latency))
        self.db.flush()
        return {"result": result, "status": status, "latency_ms": latency}

    def stream(self, text: str) -> Iterator[dict]:
        self._start_assistant()
        self.db.commit()
        if self.session.mode == "llm" and self.provider is not None:
            try:
                yield from self._llm_stream(text)
                return
            except Exception as exc:  # noqa: BLE001 - 大模型为外部依赖，任意异常都必须降级保可用
                self.db.rollback()
                self.assistant = None
                self._start_assistant()
                self.db.commit()
                yield {"type": "fallback",
                       "reason": f"大模型调用失败（{exc.__class__.__name__}），已降级规则模式"}
        else:
            yield {"type": "mode", "mode": "rule"}
        yield from self._rule_stream(text)

    # ---- 规则模式 ----
    def _rule_plan(self, text: str) -> list[str]:
        if any(k in text for k in ("创建建议", "生成建议", "建个建议", "建建议")):
            return ["optimize_menu", "__auto_suggestion__"]
        plan = [name for keywords, name in RULE_INTENTS
                if any(k in text for k in keywords)]
        return (plan or ["query_metrics"])[:3]

    def _auto_suggestion_args(self, optimize_result: dict) -> dict:
        remove = optimize_result.get("remove_samples") or []
        dish = remove[0] if remove else None
        title = f"菜单调整建议：{dish['name']}" if dish else "菜单结构调整建议"
        return {"type": "menu_change", "title": title,
                "content": {"dish_id": dish["dish_id"] if dish else None,
                            "action": "汰换" if dish else "结构调整",
                            "reason": "多目标打分处于底部区间且满足档口下限约束",
                            "score": dish["score"] if dish else None},
                "run_id": optimize_result.get("run_id")}

    def _rule_stream(self, text: str) -> Iterator[dict]:
        plan = self._rule_plan(text)
        outputs: list[tuple[str, dict]] = []
        optimize_result: dict = {}
        for name in plan:
            if name == "__auto_suggestion__":
                if not optimize_result:
                    yield {"type": "tool_call", "tool": "optimize_menu", "args": {}}
                    outcome = self._call_tool("optimize_menu", {})
                    yield {"type": "tool_result", "tool": "optimize_menu",
                           "status": outcome["status"], "latency_ms": outcome["latency_ms"],
                           "summary": summarize_result(outcome["result"], 300)}
                    optimize_result = outcome["result"]
                    outputs.append(("optimize_menu", optimize_result))
                args = self._auto_suggestion_args(optimize_result)
                name = "create_suggestion"
            else:
                args = {}
            yield {"type": "tool_call", "tool": name, "args": args}
            outcome = self._call_tool(name, args)
            yield {"type": "tool_result", "tool": name, "status": outcome["status"],
                   "latency_ms": outcome["latency_ms"],
                   "summary": summarize_result(outcome["result"], 300)}
            outputs.append((name, outcome["result"]))
            if name == "optimize_menu":
                optimize_result = outcome["result"]
        answer = "\n".join(self._compose(name, result) for name, result in outputs)
        self.assistant.content = answer
        self.db.commit()
        yield {"type": "message", "content": answer}
        yield {"type": "done", "message_id": self.assistant.id, "mode": "rule"}

    def _compose(self, name: str, result: dict) -> str:
        if "error" in result:
            return f"工具 {name} 执行失败：{result['error']}"
        if name == "query_metrics":
            k = result["kpis"]
            satisfaction = k["satisfaction"] if k["satisfaction"] is not None else "-"
            return (f"区间 {result['range']['start']}～{result['range']['end']}：营收 "
                    f"¥{k['revenue']:,}，订单 {k['orders']:,} 单，客单价 ¥{k['avg_value']}，"
                    f"毛利率 {k['gross_margin'] * 100:.1f}%，浪费率 "
                    f"{k['waste_rate'] * 100:.1f}%，满意度 {satisfaction}。")
        if name == "analyze_portfolio":
            q = result["quadrant_counts"]
            slow = "、".join(s["name"] for s in result["slow_movers"]) or "无"
            return (f"菜品组合：明星 {q.get('明星', 0)} 个、金牛 {q.get('金牛', 0)} 个、"
                    f"问题 {q.get('问题', 0)} 个、瘦狗 {q.get('瘦狗', 0)} 个；"
                    f"滞销预警示例：{slow}。")
        if name == "forecast_demand":
            if "latest_run" in result:
                r = result["latest_run"]
                return f"最近一次预测（运行 #{r['id']}）：MAE {r['mae']}，MAPE {r['mape']}。"
            m = result["metrics"]
            return (f"回测完成（运行 #{result['run_id']}）：Holt-Winters MAE {m['holt_winters']['mae']}，"
                    f"同子集基线 MAE {m['seasonal_naive_same_subset']['mae']}；"
                    f"预计日节约 {result['total_estimated_saving']} 份备餐。")
        if name == "optimize_menu":
            samples = "、".join(d["name"] for d in result["remove_samples"]) or "无"
            return (f"菜单优化（运行 #{result['run_id']}）：推广 {result['counts'].get('推广', 0)}、"
                    f"保留 {result['counts'].get('保留', 0)}、汰换 {result['counts'].get('汰换', 0)}；"
                    f"建议汰换示例：{samples}。")
        if name == "analyze_reviews":
            s = result["sentiment_dist"]
            tags = "、".join(list(result["top_tags"])[:5]) or "无"
            return (f"评价 {result['count']} 条，均分 {result['avg_rating']}；"
                    f"正面 {s.get('pos', 0)}、中性 {s.get('neu', 0)}、负面 {s.get('neg', 0)}；"
                    f"高频标签：{tags}。")
        if name == "detect_waste":
            return (f"区间浪费率 {result['totals']['rate'] * 100:.1f}%，"
                    f"预警 {result['alert_count']} 个菜品。")
        if name == "create_suggestion":
            return (f"已创建建议工单 #{result['suggestion_id']}（{result['status_label']}），"
                    f"需经理在「建议工单」页审批后生效。")
        if name == "generate_report":
            return f"周报已生成（报告 #{result['report_id']}，区间 {result['period']}），可在报告中心查看。"
        return json.dumps(result, ensure_ascii=False)[:300]

    # ---- 大模型模式 ----
    def _llm_stream(self, text: str) -> Iterator[dict]:
        yield {"type": "mode", "mode": "llm"}
        messages = [{"role": "system",
                     "content": SYSTEM_PROMPT.format(today=date.today().isoformat())}]
        messages += self.history
        messages.append({"role": "user", "content": text})
        tools = openai_tools()
        for _ in range(settings.agent_max_steps):
            reply = self.provider.chat(messages, tools)
            tool_calls = reply.get("tool_calls") or []
            if not tool_calls:
                answer = reply.get("content") or "（模型未返回内容，请换个问法。）"
                self.assistant.content = answer
                self.db.commit()
                yield {"type": "message", "content": answer}
                yield {"type": "done", "message_id": self.assistant.id, "mode": "llm"}
                return
            messages.append({
                "role": "assistant", "content": reply.get("content") or "",
                "tool_calls": [{"id": tc["id"], "type": "function",
                                "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                               for tc in tool_calls],
            })
            for tc in tool_calls:
                try:
                    args = json.loads(tc["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                yield {"type": "tool_call", "tool": tc["name"], "args": args}
                outcome = self._call_tool(tc["name"], args)
                yield {"type": "tool_result", "tool": tc["name"],
                       "status": outcome["status"], "latency_ms": outcome["latency_ms"],
                       "summary": summarize_result(outcome["result"], 300)}
                messages.append({"role": "tool", "tool_call_id": tc["id"],
                                 "content": summarize_result(outcome["result"], 4000)})
        answer = "已达到单轮工具调用上限，请缩小问题范围后再试。"
        self.assistant.content = answer
        self.db.commit()
        yield {"type": "message", "content": answer}
        yield {"type": "done", "message_id": self.assistant.id, "mode": "llm"}