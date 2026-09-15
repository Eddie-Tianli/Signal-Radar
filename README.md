# SignalRadar v0.1.0

SignalRadar 是面向 Windows 单用户本地运行的个人信息情报工具。围绕关注的主题（Topic）采集内容（Item），通过本地 AI 判断相关性并生成简报（Digest）。MockSource 让采集流程无需真实外部 API 即可测试。

## 当前功能

- 概览（Dashboard）：主题、内容、相关内容和待分析数量，最新简报、近期内容及本地依赖状态。
- Topic 创建、查看、编辑、删除和启用状态管理；手动扫描及内容展示。
- YouTube Data API 与仅供开发测试的 MockSource；按来源标识去重。
- Ollama 结构化分析：单条分析、有限数量的批量分析，保存相关性、评分、分类、摘要和分析时间。
- 从最多 20 条已分析的相关 Item 生成 Digest，支持查看历史简报。
- 可选自动任务（Scheduler）：扫描 → 分析待处理内容 → 有新相关内容时生成简报。
- 自动生成简报成功且有新相关内容时，可发送 Windows 通知。
- 本地启动脚本、依赖检查、正常关闭和轮转日志。

## 技术栈与架构

前端：Next.js + React + TypeScript + Tailwind CSS。后端：Python + FastAPI。
数据库：PostgreSQL + SQLAlchemy + Alembic。AI：本地 Ollama。
Scheduler 使用 Python 标准库；Windows 通知使用 WinRT。

```text
Topic → SourceAdapter → Item → AIProvider / Ollama → Relevant Items → Digest
                         ↓                              ↓
                      PostgreSQL ←─────────────────────┘
                         ↓
                  Dashboard / Topics UI
```

Scheduler 调用同一组服务，通知在自动简报保存成功后发送。
项目使用 monorepo：`frontend/`、`backend/`、`docs/`。当前 migration head 为 **0004**，项目版本为 **0.1.0**。

## 本地安装与启动

准备 Python、Node.js/npm、本地 PostgreSQL，以及已安装模型的 Ollama。
启动顺序：**PostgreSQL → Ollama → SignalRadar**。Ollama 离线时仍可浏览数据，但分析和简报生成不可用。

在仓库根目录的 PowerShell 中执行首次配置：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
# Only if .env does not exist: copy .env.example .env
# Edit .env with local database credentials and the exact Ollama model name.
python -m alembic upgrade head
cd ..\frontend
npm install
cd ..
.\start-signalradar.ps1 -CheckOnly
.\start-signalradar.ps1
```

数据库账户创建见 [后端说明](backend/README.md)。已有 `.env` 时不要覆盖；不要提交凭据。
启动脚本会构建 Next.js 并使用生产模式运行。只有构建与当前源码一致时才使用 `-SkipBuild`。
保持终端打开，按 Ctrl+C 正常关闭前后端。访问 http://localhost:3000；Swagger 位于 http://127.0.0.1:8000/docs。日志位于 `logs/`。

## 环境变量

在 `backend/.env` 中配置；进程环境变量优先。修改后重启后端。

| 环境变量 | 默认值 / 用途 |
| --- | --- |
| DB_HOST | 127.0.0.1 |
| DB_PORT | 本项目本地模板为 9912 |
| DB_NAME / DB_USER / DB_PASSWORD | PostgreSQL 数据库、账户和密码；密码必填 |
| USE_MOCK_SOURCE | false；true 使用固定模拟内容 |
| YOUTUBE_API_KEY | 仅真实 YouTube 采集需要 |
| OLLAMA_BASE_URL | http://localhost:11434；仅支持本机回环 HTTP |
| OLLAMA_MODEL | 使用 ollama list 中已安装模型的完整名称，无业务代码默认值 |
| SCHEDULER_ENABLED | false；是否启用自动任务 |
| SCAN_INTERVAL_MINUTES | 60；支持 0.1–10080 分钟 |
| NOTIFICATIONS_ENABLED | false；是否启用 Windows 通知 |

脚本不会自动安装服务、注册开机启动、下载模型或修改 Windows 配置。

## MockSource 与 Ollama

设置 `USE_MOCK_SOURCE=true` 可进行本地验收。每个 query 返回 3 条 ID 稳定的模拟内容，重复扫描计入 duplicates。链接是本地占位地址，模拟内容不代表真实新闻。

启动 Ollama，运行 `ollama list`。验收机器使用 `deepseek-r1:8b`，请按自己的实际安装情况配置 `OLLAMA_MODEL`。MockSource 只模拟采集，分析和生成简报仍调用真实本地模型。AI 输出已标注，可能存在错误；系统不抓取全文。

## 日常使用

1. 在“概览”查看统计和运行状态。
2. 在“主题”创建关注主题，点击“扫描”和“查看内容”。
3. 单独“分析”，或“分析未处理内容”（每次最多 10 条）。
4. 存在相关内容后点击“生成简报”，查看最新或历史简报。
5. 刷新概览以更新数据快照；主题链接跳转到对应卡片。

自动运行时设置 `SCHEDULER_ENABLED=true`，使用单个后端进程，不使用 reload 或多个 worker。首次等待配置间隔；后续在上一轮完成后再等待。每轮每个 Topic 最多分析 20 条待处理内容，无新相关内容则不生成简报。避免手动操作与自动任务竞争。

设置 `NOTIFICATIONS_ENABLED=true` 可启用通知。Windows 将其归到 Windows PowerShell；专注助手或通知设置可能阻止横幅。手动生成简报不通知。安全关闭自动任务：Ctrl+C → 设置 `SCHEDULER_ENABLED=false` → 重启。

## 验证

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
$env:RUN_POSTGRES_TESTS='1'
python -m pytest -q -p no:cacheprovider --basetemp "$env:TEMP\sr-tests-$([guid]::NewGuid().ToString('N'))"
Remove-Item Env:\RUN_POSTGRES_TESTS
python -m alembic current
python -m alembic check
cd ..\frontend
npm run lint
npm run build
```

自动化测试不调用真实模型或信息源，不弹系统通知。实际验收见 [v0.1.0 验收记录](docs/development/v0.1.0-acceptance.md)，详细操作见 [本地开发指南](docs/development/local-development)。

## 当前限制

- 单用户本地应用，无登录、多用户、云部署或手机 App。
- 真实 YouTube 搜索需要 Key 和配额，暂无其他真实信息源。
- AI 依赖本地 Ollama 和计算资源，推理可能超时。
- Windows 通知需要交互登录会话及允许通知的系统设置。
- 不安装后台系统服务，不提供开机自启或 Windows 重启、休眠后的恢复机制。
- Scheduler 锁仅在单进程内生效，无持久化重试队列；分析成功但简报失败时可手动生成。
- `(source, external_id)` 全局唯一，同一 Item 只属于一个 Topic。
- 内容及简报历史尚无分页；概览近期列表最多 5 条。
- 无事件聚类、embedding、Vector DB 或 RAG。

## 后续规划（尚未实现）

- 根据本地使用反馈改善可靠性与易用性。
- 按实际需要评估分页和更多信息源。
- 本地流程稳定后再评估更高级的内容组织方式。

本次没有开发 v0.2.0 功能。
