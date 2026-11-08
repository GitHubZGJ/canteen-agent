# 架构设计

## 简介

本文档是《面向校园食堂经营的就餐数据分析与菜品优化智能体设计与实现》的技术架构设计，与 [项目规划](project-plan.md) 配套。读者是开发者本人，用于指导实现与面试讲解。文档先于代码冻结，实现期间如需偏离，先改文档再改代码。

## 总体架构

系统采用前后端分离的模块化单体：后端单进程部署，内部模块边界清晰；不拆微服务，降低部署与讲解成本。

```text
┌────────────────────────────────────────────────────┐
│ 前端 SPA：看板 / 分析 / 预测 / 工单 / 对话 / 报告      │
│ Vue 3 + TypeScript + Element Plus + ECharts         │
└───────────────────────┬────────────────────────────┘
                        │ REST + SSE（JWT 鉴权）
┌───────────────────────▼────────────────────────────┐
│ API 层：路由自动发现、统一响应、参数校验、角色鉴权     │
├────────────────────────────────────────────────────┤
│ 服务层：领域逻辑、工单状态机、报告生成、操作审计       │
├──────────────┬───────────────────┬─────────────────┤
│ 智能体编排    │ 分析引擎           │ 预测与优化       │
│ 计划-执行循环 │ 指标/四象限/预警   │ 预测/多目标打分  │
├──────────────┴───────────────────┴─────────────────┤
│ 工具层：8 个注册工具，schema 校验、权限与审计          │
├────────────────────────────────────────────────────┤
│ 数据层：SQLAlchemy 2 + Alembic（SQLite / PostgreSQL） │
└────────────────────────────────────────────────────┘
外部依赖：OpenAI 兼容 LLM API（可选，无 Key 走规则降级）
```

依赖方向自上而下：API 层调用服务层，服务层调用分析引擎与工具层，智能体只能通过工具层触达数据。分析引擎是纯函数，不访问数据库，便于单测与讲解。

## 目录结构

```text
canteen-agent/
├── backend/
│   ├── app/
│   │   ├── api/            # 路由模块，自动发现
│   │   ├── core/           # 配置、安全、统一响应、异常
│   │   ├── models/         # SQLAlchemy ORM
│   │   ├── schemas/        # Pydantic 入参与出参
│   │   ├── services/       # 领域逻辑与工单状态机
│   │   ├── analytics/      # 指标、四象限、预测、优化（纯函数）
│   │   ├── agent/          # 编排器、LLM 适配、规则降级
│   │   ├── tools/          # 智能体工具注册表
│   │   └── reports/        # 周报生成
│   ├── alembic/            # 数据库迁移
│   ├── tests/              # pytest 单元与集成测试
│   └── scripts/            # 数据生成、启动、验证脚本
├── frontend/
│   └── src/
│       ├── api/            # axios 封装与类型定义
│       ├── views/          # 页面
│       ├── components/     # ChartPanel 等封装
│       ├── stores/         # Pinia
│       └── router/
├── data/                   # 模拟数据与导入模板（进仓库）
├── docs/                   # 中文文档与模块一页纸
├── docker-compose.yml
├── .env.example
├── .github/workflows/ci.yml
├── README.md
└── LICENSE
```

## 后端模块职责

| 模块 | 职责 | 关键约束 |
| --- | --- | --- |
| api | 参数校验、调用服务、组装响应 | 不写业务逻辑 |
| core | 配置、JWT、统一响应、全局异常 | 配置只读 `.env` |
| services | 领域逻辑、事务、工单状态机 | 唯一允许开启事务的层 |
| analytics | 指标口径、四象限、预测、优化 | 纯函数，输入 DataFrame 输出结果 |
| agent | 编排循环、LLM 适配、降级 | 不直接访问数据库 |
| tools | 工具注册、schema 校验、审计 | 智能体触达数据的唯一入口 |
| reports | 周报组装 | 只读服务层接口 |

路由自动发现：`app/api/` 下每个模块暴露 `router`，启动时用 `pkgutil` 扫描注册，新增模块零改动接线。

## 数据库设计

### 表分组

| 分组 | 表 | 说明 |
| --- | --- | --- |
| 主数据 | user、canteen、stall、dish | 用户、食堂、档口、菜品（含成本与营养 JSON） |
| 经营事实 | orders、order_item、review、waste_record | 订单、明细、评价、浪费记录 |
| 分析结果 | forecast_run、forecast_result、optimization_run | 预测与优化留痕，参数与误差可追溯 |
| 决策闭环 | suggestion、suggestion_event、suggestion_effect | 工单、状态流转事件、效果归因 |
| 智能体审计 | agent_session、agent_message、tool_call_log | 会话、消息、工具调用日志 |
| 系统 | report、operation_log | 周报、操作日志 |

### 关键关系与索引

- dish 属于 stall，stall 属于 canteen；order_item 关联 orders 与 dish；review 可选关联订单与菜品。
- suggestion 可关联 optimization_run；suggestion_event 记录每次状态迁移；suggestion_effect 按指标存前后值。
- forecast_result 含 dish_id 与 slot，按菜品 × 时段 × 日期存预测值与上下界。
- 索引：`orders(dining_time)`、`order_item(dish_id)`、`waste_record(stall_id, date)`、`suggestion(status)`。
- 菜品营养存 `nutrition_json`（热量、蛋白质、脂肪、碳水），由生成器按食材估算并标注模拟口径。

### 迁移与方言

Alembic 版本化迁移，启动时执行 `upgrade head`。默认 SQLite 开 WAL（预写日志）模式支撑并发读；`DATABASE_URL` 切到 PostgreSQL 时代码零改动，JSON 字段用 SQLAlchemy 通用 JSON 类型。

## API 设计

### 约定

- 统一响应 `{code, msg, data}`，沿用 Result 约定；业务失败抛 BizException，由全局处理器转换。
- 鉴权用 JWT（JSON Web Token）Bearer；角色控制用 `require_role` 依赖；分页参数 `page`、`page_size`。
- 错误码分段：`0` 成功；`1xxx` 参数错误；`2xxx` 认证与权限；`3xxx` 业务错误；`5xxx` 系统错误。

### 端点清单

| 分组 | 端点 | 说明 |
| --- | --- | --- |
| 认证 | POST /api/auth/login、GET /api/auth/me | 登录、当前用户 |
| 看板 | GET /api/dashboard/overview、/trend、/ranking、/heatmap | 核心指标、趋势、档口排行、时段热力 |
| 菜品 | GET /api/dishes、/api/dishes/options、/api/dishes/{id}/analysis | 列表、下拉选项、单品分析 |
| 分析 | GET /api/analysis/portfolio、/waste、/reviews、/nutrition | 四象限、浪费、评价、营养 |
| 预测 | POST /api/forecast/runs、GET /api/forecast/runs、GET /api/forecast/runs/{id} | 发起预测、运行列表、结果与误差 |
| 优化 | POST /api/optimization/runs、GET /api/optimization/runs、GET /api/optimization/runs/{id} | 发起优化、运行列表、打分详情 |
| 工单 | GET/POST /api/suggestions、POST /api/suggestions/{id}/review、/execute、/evaluate | 闭环全部动作 |
| 智能体 | GET/POST /api/agent/sessions、POST /api/agent/sessions/{id}/messages | 会话管理；发消息返回 SSE（服务器推送事件）流 |
| 报告 | POST /api/reports/weekly、GET /api/reports、GET /api/reports/{id} | 生成、列表与详情 |
| 数据 | POST /api/data/generate、POST /api/data/import、GET /api/data/templates/{kind} | 生成模拟数据、CSV 导入、模板下载 |
| 系统 | GET /api/system/logs、GET/POST /api/system/users | 操作日志、用户管理（admin） |

SSE 事件类型：`message`（文本增量）、`tool_call`（工具名与状态）、`done`、`error`。前端用 fetch 读流，过程可视。

## 智能体架构

### 编排循环

编排器驱动大语言模型（LLM）执行「计划-执行」循环：理解意图 → 生成工具计划 → 逐步调用并观察 → 汇总答复。单轮最多 8 步，每步写 tool_call_log；超步数强制收尾并说明，防止死循环。

### LLM 适配与降级

Provider 接口只暴露 `chat(messages, tools)`，有两个实现。

- OpenAICompatProvider：`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 来自 `.env`，兼容智谱、DeepSeek、通义千问等；httpx 客户端 `trust_env=False` 直连，规避本机畸形代理变量。
- RuleBasedProvider：关键词意图识别映射到固定工具序列，覆盖「看指标、菜品分析、预测、优化、生成建议、出周报」六类高频意图。

会话创建时可指定模式：`auto`（有 Key 走大模型，无 Key 走规则）或 `rule`（强制规则）。大模型调用异常时当轮自动降级规则并标记 `fallback` 事件，保证对话始终可用。

启动时探测 Key，无 Key 自动降级，会话记录 `mode` 字段，前端明确标注「规则模式」。两种模式共用工具层，业务结果一致。

### 工具清单

| 工具 | 功能 | 读/写 |
| --- | --- | --- |
| query_metrics | 查询经营指标与时段对比 | 读 |
| analyze_portfolio | 菜品四象限与 ABC 分类 | 读 |
| forecast_demand | 指定菜品则回测该菜品；未指定时返回最近一次运行摘要并提示 | 读（留痕） |
| optimize_menu | 多目标菜单优化 | 读（留痕） |
| analyze_reviews | 评价标签与满意度分析 | 读 |
| detect_waste | 浪费风险预警 | 读 |
| create_suggestion | 创建建议工单草稿 | 写 |
| generate_report | 生成经营周报 | 读（留痕） |

### 安全与审计

- 入参用 Pydantic schema 校验，非法参数直接拒绝；查询全部走预定义参数化查询，不让模型生成自由 SQL。
- 写操作只有 create_suggestion，且只能建草稿；审批与执行必须由人在界面完成，模型无权直接改经营数据。
- 评价等外部文本作为数据传入并加分隔标记，降低提示注入风险；工具结果截断到约定长度。
- 每次调用记录工具名、入参、结果摘要、耗时与状态，前端可展开追溯。

## 分析与算法设计

### 指标口径

| 指标 | 口径 |
| --- | --- |
| 营收 | `sum(order_item.amount)`，按自然日聚合 |
| 客单价 | 营收 / 订单数 |
| 毛利率 | `(收入 - 成本) / 收入`，成本取菜品成本卡 |
| 浪费率 | 浪费量 / 备餐量，按菜品与日期聚合 |
| 满意度 | 评价评分均值，辅以标签频次 |
| 滞销 | 连续 7 天日销量低于档口均值的 20% |

口径集中在 analytics 模块一处定义，看板、工具、周报共用，避免数出多门。接口默认区间锚定数据最大日期（往前 30 天），不用系统当天，保证模拟数据开箱有数。

### 菜品组合分析

以销量中位数和毛利率中位数切四象限：明星（双高）、金牛（高毛利低销量）、问题（高销量低毛利）、瘦狗（双低）。ABC 分类按营收贡献累计占比 70%、20%、10% 切分。滞销与浪费预警按上述口径每日计算。

### 备餐量预测

- 基线：季节朴素法，取上周同日同时段销量。
- 模型：霍尔特-温特斯（Holt-Winters）三次指数平滑，statsmodels 实现，加法季节，按菜品聚合到日 × 时段。
- 回测：留出最后 14 天，输出 MAE（平均绝对误差）与 MAPE（平均绝对百分比误差）；有效天数不足 28 或总量不足 50 的菜品回退到档口均值并标注。
- 预测区间：按回测残差标准差的 ±1.96σ 给出上下界，下界截断到 0。
- 备餐建议：预测量 × 安全系数（默认 1.1），对比历史浪费测算可节约量。

### 菜单优化

多目标加权打分：`score = w1·毛利 + w2·满意度 + w3·营养均衡 + w4·(1 - 浪费率)`，各指标先归一化，权重默认 0.4、0.3、0.15、0.15 且可调。约束包括保底菜品与档口供应上限；按打分排序产出汰换、保留、推广建议。算法手写、固定种子，结果可复现，每一步可解释。

### 效果归因

工单执行后进入评估期（默认 14 天），对比执行前后等长窗口的销量、毛利与浪费率，写入 suggestion_effect。复盘明确标注「前后对比，非严格因果」，避免过度宣称。评估窗口按实际可用天数计算并在复盘中标注，演示数据可立即评估。

## 前端架构

| 路由 | 页面 | 要点 |
| --- | --- | --- |
| /login | 登录 | JWT 存 localStorage，过期重新登录 |
| /dashboard | 经营大屏 | 指标卡、趋势图、时段热力、排行 |
| /dishes | 菜品分析 | 四象限散点、ABC 表、滞销预警 |
| /forecast | 预测备餐 | 发起预测、区间图、误差对比 |
| /optimization | 菜单优化 | 权重调整、保底选择、打分与动作 |
| /suggestions | 建议工单 | 状态看板、审批、执行登记、归因图 |
| /agent | 智能体对话 | SSE 流式、工具调用过程展开 |
| /reports | 报告中心 | 周报预览与导出 |
| /data | 数据管理 | 生成模拟数据、CSV 导入 |
| /system | 系统管理 | 用户与日志（admin） |

API 层统一 axios 封装，类型集中在 `api/types.ts`；图表统一走 ChartPanel.vue 封装 ECharts；状态用 Pinia（auth、app 两个 store）。除登录页外，全部路由由守卫校验 JWT 与角色。

## 数据流

模拟生成或 CSV 导入 → 校验入库 → 服务层按口径聚合 → 看板与分析页展示；智能体经工具层走同一套口径。

建议工单从分析结果诞生，经人工审批与执行登记，评估期结束后归因归档，周报自动引用工单进展。MVP（最小可行产品）阶段直接 SQL 聚合加索引；数据量超预期再引入日汇总表，届时补一条 ADR。

## 安全设计

- 密码用 bcrypt 哈希；JWT 有效期 24 小时，登录接口限速。
- 角色三级：admin、manager、viewer；工具写权限与工单审批分离。
- 密钥只存 `.env`，不进仓库不进数据库；CORS（跨域资源共享）白名单；操作日志覆盖全部写动作。
- CI 跑 gitleaks 密钥扫描，提交前本地再扫一次。

## 部署与运行

本地开发：后端虚拟环境与依赖全部装在 `backend/.venv` 与项目目录内；前端依赖在项目 `node_modules`；`scripts/` 提供启动与验证脚本。Docker Compose 起 backend、frontend（nginx）两个服务，可选加 PostgreSQL。

| 环境变量 | 说明 | 默认 |
| --- | --- | --- |
| DATABASE_URL | 数据库连接 | SQLite（项目内文件） |
| JWT_SECRET | 签名密钥 | 无，必填 |
| LLM_BASE_URL / LLM_API_KEY / LLM_MODEL | 大模型接入 | 空，自动降级 |
| AGENT_MAX_STEPS | 单轮最大工具步数 | 8 |

## 关键设计决策

| 决策 | 选择 | 理由与放弃方案 |
| --- | --- | --- |
| 架构形态 | 模块化单体 | 单人项目易部署易讲解；放弃微服务 |
| 默认数据库 | SQLite | 零配置克隆即跑；PostgreSQL 留扩展口 |
| 无 Key 策略 | 规则降级 | 保证可运行与可测试；放弃强依赖外部 API |
| 建议落地 | 人工审批工单 | 模型不直改经营数据，安全且形成闭环 |
| 优化算法 | 手写加权打分 | 可解释可复现；放弃黑盒求解器 |
| 模型权重 | 不依赖模型权重下载 | 本机 Hugging Face 不可达；放弃本地 embedding 模型 |
| 前端语言 | TypeScript | 类型即文档，利于讲解；放弃纯 JS |

实现时每个模块补一页纸说明放 `docs/modules/`，关键偏离补 ADR，保证代码本人能讲清。