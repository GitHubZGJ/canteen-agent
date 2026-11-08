# 部署手册

## 简介

本手册覆盖本地开发、Docker Compose 部署、环境变量、数据初始化与常见问题。模块与接口设计见 [架构设计](architecture.md)。

## 环境要求

| 组件 | 版本 | 用途 |
| --- | --- | --- |
| Python | 3.12 及以上 | 后端与数据脚本 |
| Node.js | 22 及以上 | 前端开发与构建 |
| Docker | 24 及以上（可选） | 容器化部署 |

## 本地开发

在项目根目录准备配置：

```bash
cp .env.example .env
```

编辑 `.env`，至少填写 `JWT_SECRET`（任意随机串）；大模型三项可留空，系统自动使用规则模式。

后端：

```bash
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe scripts/dev.py start        # 自动迁移 + 播种演示账号
.venv/Scripts/python.exe scripts/generate_data.py    # 生成 180 天模拟数据
```

接口文档：http://127.0.0.1:8000/docs 。Linux 与 macOS 把 `.venv/Scripts/python.exe` 换成 `.venv/bin/python`。

前端：

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 ，Vite 会把 `/api` 代理到 `127.0.0.1:8000`。演示账号见 README。

## Docker Compose 部署

```bash
cp .env.example .env     # 至少修改 JWT_SECRET
docker compose up -d --build
docker compose exec backend python scripts/generate_data.py
```

- 前端：http://localhost:8080
- 接口文档：http://localhost:8000/docs
- 数据库持久化在数据卷 `canteen-data`（容器内 `/data/canteen.db`）
- 停止并保留数据：`docker compose down`
- 停止并删除数据：`docker compose down -v`（谨慎）

## 环境变量

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| DATABASE_URL | 数据库连接；本地默认项目内 SQLite | 项目内 `data/canteen.db` |
| JWT_SECRET | JWT 签名密钥，生产必填高强度随机值 | 无，必填 |
| JWT_EXPIRE_HOURS | token 有效期（小时） | 24 |
| LLM_BASE_URL / LLM_API_KEY / LLM_MODEL | OpenAI 兼容大模型接入 | 空，自动规则模式 |
| AGENT_MAX_STEPS | 智能体单轮最大工具步数 | 8 |

Docker 场景下 compose 会把 `DATABASE_URL` 覆盖为 `sqlite:////data/canteen.db`，`.env` 中的该值只影响本地开发。

## 数据初始化与导入

- 命令行生成：`python scripts/generate_data.py --days 180 --seed 42 --reset`
- 数据管理页（管理员或经理）：生成模拟数据、下载模板、导入菜品 / 订单 / 评价三类 CSV
- CSV 模板源文件：`backend/app/data_templates/`
- 导入规则：逐行校验，合法行入库，错误行返回行号与原因；单次最多 5000 行、5 MB

## 常见问题

| 问题 | 处理 |
| --- | --- |
| 端口被占用 | 后端固定 8000、前端 5173、Docker 前端 8080；改端口时同步调整 Vite 代理与 compose |
| 本机代理变量导致请求异常 | 后端大模型客户端已用 `trust_env=False` 直连；其他工具请自行清理畸形代理变量 |
| 大模型返回 429 | 免费模型存在限流，稍后重试或更换模型；对话会自动降级规则模式 |
| 没有大模型 Key | 规则模式覆盖全部核心功能，不影响演示与测试 |
| 迁移失败 | 删除本地 `data/canteen.db` 后重启，或手动执行 `alembic upgrade head` |
| 数据需要重置 | 数据管理页勾选「清空重建」，或执行 `generate_data.py --reset` |

## 生产部署注意事项

- 立即修改三个演示账号密码，并使用高强度 `JWT_SECRET`。
- 在前置反向代理启用 HTTPS，限制 `/docs` 与调试接口的公网访问。
- 定期备份 SQLite 文件（`data/canteen.db`）；并发要求高时切换 PostgreSQL，只需替换 `DATABASE_URL`。
- 保留 `operation_log` 与 `tool_call_log`，便于审计智能体行为。