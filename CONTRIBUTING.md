# 贡献指南

## 开发环境

见 [README 快速开始](README.md) 或 [部署手册](docs/deployment.md)。

## 提交前检查

```bash
cd backend
.venv/Scripts/python.exe -m ruff check app scripts tests
.venv/Scripts/python.exe -m pytest tests -q
.venv/Scripts/python.exe -X utf8 scripts/scan_secrets.py

cd ../frontend
npm run build
```

后端改动需保证 pytest 全绿；涉及页面的改动请运行 `npm run ui:check`（本机 Edge 无头）并复核截图。

## 代码约定

- 分层：`api` 只做参数校验与响应组装；业务在 `services`；`analytics` 必须是纯函数（不访问数据库）；智能体只能通过 `tools` 触达数据。
- 指标口径唯一定义在 `analytics/metrics.py` 与 `analytics/portfolio.py`，新增指标先补口径函数与手算测试。
- 写操作必须做角色校验并写 `operation_log`；智能体写操作只允许创建建议草稿。
- 未知输入一律走 `BizException` 并给出明确中文消息；负向测试要同时断言错误码与消息。
- 提示词或工具 schema 变更时，同步更新 `docs/architecture.md`。

## 新增一个智能体工具

1. 在 `app/tools/business_tools.py` 用 `@tool` 注册，并提供 Pydantic 参数模型。
2. 工具内部复用 `services`，不要直接写 SQL。
3. 如需规则模式覆盖，在 `app/agent/engine.py` 的意图表登记关键词。
4. 补一条工具契约测试（合法参数、非法参数、权限）。

## 提交信息

使用 `feat` / `fix` / `docs` / `refactor` / `test` / `chore` 前缀，中文描述即可，示例：`feat: 新增备餐预测区间`。

## 问题反馈

提交 issue 时附：复现步骤、期望结果、实际结果、相关日志（隐去密钥与个人信息）。