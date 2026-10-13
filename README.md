# SignalRadar v0.2.0（本地候选版本）

SignalRadar 是面向 Windows 单用户本地运行的个人信息情报工具。用自然语言描述关注意图，设置包含与排除条件，再通过现有一键更新完成采集、相关性分析、有效信息筛选、信息整合和中文简报。

本版本不创建发布 Tag。实施过程及真实验收结果见 [v0.2.0 验收记录](docs/development/v0.2.0-implementation.md)。

## 当前功能

- 中文 Dashboard、Topic 管理、内容筛选/排序、简报阅读及回收站。
- Topic 支持 name、description、逐条 include / exclude 规则、0～1 阈值（默认 0.80）、enabled。
- Query Builder 根据名称、描述与启用的包含条件提取关键词；内置 ChatGPT 模型、诺兰新电影简短模板，其他主题采用保守提取。最多 2 查询，不调用 AI 改写；不是通用自然语言翻译器。
- YouTube Data API / MockSource 将内容统一保存为 Item；实际执行查询与最近成功扫描时间可查看。
- Ollama 逐条输出符合度、理由、排除状态、分类和事实摘要。程序统一判定有效、无效、待复核、失败。
- YouTube 播放/点赞/评论等真实指标单独计算热度；MockSource 与缺失指标显示未知。
- 当前有效摘要经保守去重后生成中文 Digest，保存来源 Item ID、URL、时间和作者快照；旧版简报继续可读。
- 手动、一键更新和 Scheduler 复用同一逻辑；规则改变会使旧分析过期，不无条件进入新简报。
- 可选 Windows 通知、本地启动脚本、依赖状态、标准日志及默认关闭的 Ollama Trace。
- 单条 Item（连同 AI 结果）及 Digest 可移入回收站、恢复和二次确认永久删除。

## 技术栈与架构

Next.js + React + TypeScript + Tailwind CSS；Python + FastAPI；PostgreSQL + SQLAlchemy + Alembic；本地 Ollama。Scheduler 使用 Python 标准库，Windows 通知使用 WinRT，没有新 AI 框架或前端依赖。

```text
Topic 描述 / 规则 / 阈值
→ Query Builder → SourceAdapter → Raw Item → PostgreSQL
→ AIProvider / Ollama → 符合度与排除理由
→ 程序有效性判定 → 保守信息整合 → Final Digest
→ PostgreSQL（来源快照）→ Frontend
```

项目采用 monorepo：`frontend/`、`backend/`、`docs/`。版本 **0.2.0**，Alembic head **0006**。

## 本地安装与启动

启动顺序：**PostgreSQL → Ollama → SignalRadar**。Ollama 不可用时仍可管理主题、扫描和阅读已有数据。

```powershell
cd D:\Projects_ltl\Signal-Radar\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
# 仅当 .env 不存在时复制；保留现有数据库凭据和本机模型名称
# Copy-Item .env.example .env
python -m alembic upgrade head
python -m alembic current
python -m alembic check
cd ..\frontend
npm install
cd ..
.\start-signalradar.ps1 -CheckOnly
.\start-signalradar.ps1
```

已有项目无需重建虚拟环境。升级前停止旧进程并备份数据库，应用 `0006_intent_pipeline.py`。迁移只增加字段和表；旧 Raw Item、AI 结果与 Digest 均保留，旧分析标为待重新确认。不要用降级来启动旧代码。

访问 http://localhost:3000；Swagger：http://127.0.0.1:8000/docs。保持终端打开，Ctrl+C 正常停止。脚本构建生产前端并启动单进程后端；只有构建与源码一致时才用 `-SkipBuild`。脚本不会修改系统配置或重复启动 PostgreSQL / Ollama。数据库账户配置见 [后端说明](backend/README.md)。

## 环境变量

在 `backend/.env` 配置，修改后重启；进程环境变量优先。不要提交 `.env`。

| 环境变量 | 默认值 / 用途 |
| --- | --- |
| DB_HOST / DB_PORT | 127.0.0.1 / 9912 |
| DB_NAME / DB_USER / DB_PASSWORD | 数据库与凭据，密码必填 |
| USE_MOCK_SOURCE | false；true 仅模拟采集 |
| YOUTUBE_API_KEY | 真实 YouTube 需要有效 Key 与配额 |
| OLLAMA_BASE_URL | http://localhost:11434；只允许本机回环 HTTP |
| OLLAMA_MODEL | `ollama list` 中的完整模型名称，例如本机 `deepseek-r1:8b` |
| OLLAMA_NO_THINK_HINT | false；可选 `/no_think` 兼容提示，仅适用于支持该提示的模型，不保证停止 thinking |
| OLLAMA_TRACE_ENABLED | false；显式开启才保存完整 Prompt 和模型回复 |
| SCHEDULER_ENABLED | false；是否自动更新 enabled Topic |
| SCAN_INTERVAL_MINUTES | 60；0.1～10080 分钟 |
| NOTIFICATIONS_ENABLED | false；Windows 通知开关 |

Trace：`backend/logs/ollama_trace.jsonl`。可能含私人 Topic、原文和模型回复，不能公开上传；关闭后不会自动删除历史文件。

## 日常使用

1. 创建 Topic，描述主要关注需求，逐条添加包含与排除条件。
2. 阈值默认 0.80，表示 AI 估计符合度达到 80%；它不是客观概率、准确率或传播热度。
3. 点击“一键更新”，查看实际查询和每阶段数量；每轮最多分析 20 条待处理、失败或配置过期 Item。
4. 只有 `score >= threshold` 且 `exclusion_status=not_excluded` 才有效；uncertain 或明确规则冲突进入待复核。
5. 查看 Item 的理由与原始 metadata；无效内容仍保留，可手动重新分析。来源身份未知时不能仅凭频道名认定官方/粉丝。
6. 在简报页阅读中文简报与来源快照。默认从最高符合度、较新的有效内容中选最多 15 条，整合成最多 10 单元。
7. 高级操作可独立扫描、分析待处理或过期内容、生成简报。显式手动生成会保存新快照；自动流程仅在有效输入指纹改变时生成。

同一 Topic 的更新、分析、规则编辑、删除与恢复使用进程内互斥，忙碌返回 409。进度是本次 NDJSON 响应，不是永久任务；断线后应刷新已保存结果再决定重试。

### 符合度与热度

符合度来自 AI 的语义判断；热度仅来自对应平台实际统计。YouTube 热度使用播放量每日速率的对数归一化，以及可用点赞率/评论率；缺失指标不补 0，发布时间或播放量未知则热度未知。低热度不影响有效性，不与其他 Source 横向比较。算法详见 [系统设计](docs/architecture/system-design.md)。

### 配额与能力边界

一次 Scan 最多 2 次 `search.list`（各 15 条）及 1 次批量 `videos.list(part=statistics)`，无分页、无自动网络重试。重复扫描也消耗配额；查询不是来源身份认证。实际配额以 Google Cloud Console 和官方文档为准：[search.list](https://developers.google.com/youtube/v3/docs/search/list)、[videos.list](https://developers.google.com/youtube/v3/docs/videos/list)。

仅获取视频 metadata 和统计，**未观看或理解完整视频，不下载视频、不抓字幕或全文**。网络/配额导致部分搜索或统计失败时，在已有发现的情况下保留 Raw Item 并返回 warnings；没有任何成功搜索则明确失败。

### MockSource、Scheduler 与通知

`USE_MOCK_SOURCE=true` 时每个 query 返回 3 条稳定模拟内容；2 查询可返回 6 条，改变查询可能产生新的模拟 ID。它不是正式来源，内容和本地链接不代表真实新闻。MockSource 不模拟 AI，默认分析仍需要本地 Ollama。

Scheduler 与手动更新使用同一 TopicUpdateService。安全试用时先保持关闭；开启后使用单个后端进程，不使用 reload 或多 worker。没有有效摘要输入变化时跳过自动简报；显式重新分析且结果未变也不会重复自动生成。Windows 通知只在本轮有新有效 Item 且已保存新 Digest 时发送，错误只写日志。安全关闭：Ctrl+C → `SCHEDULER_ENABLED=false` → 重启。

### 删除与回收站

Item 的原文和 AI 结果一起移入/恢复；Digest 保留全文与来源快照。回收站不自动清理，不参与分析、统计或简报输入。软删除 Item 仍占用来源唯一标识，重复扫描不会自动恢复；永久删除后可能再次采集。软删除 Digest 仍作为自动生成指纹水位，避免自动重建；永久删除最新 Digest 后可能重新生成。

**删除整个 Topic 会永久级联删除全部内容及回收站，无法恢复。** 删除 Item 不改写已有简报来源快照。

## 验证

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
$env:RUN_POSTGRES_TESTS='1'
New-Item -ItemType Directory -Path D:\pytest-temp -Force | Out-Null
$testTempPath = Join-Path 'D:\pytest-temp' ([guid]::NewGuid().ToString('N'))
python -m pytest -q --tb=short -p no:cacheprovider --basetemp $testTempPath
Remove-Item Env:\RUN_POSTGRES_TESTS
python -m alembic current
python -m alembic check
cd ..\frontend
npm run test:api
npm run lint
npm run build
```

每次 pytest 必须使用新 GUID 目录，不使用 Windows 默认 Temp；自动测试不调用真实 YouTube/Ollama，不弹通知。详细人工步骤见 [本地开发](docs/development/local-development.md)。

## 当前限制与后续规划

- 单用户 Windows 本机应用，无登录、多用户、云部署、手机 App、Email 或 Telegram。
- 真实来源仅 YouTube；没有 RSS / Web Search、视频下载、字幕或全文抓取。
- Query Builder 是可解释模板/关键词提取，不是任意语言的完整意图解析器；复杂规则语义与身份判断仍可能需要人工复核。
- AI 分数不是可靠性保证；8B 模型可能误判、超时或格式失败。语言/格式/指令漂移检查不能证明事实正确，也不能彻底消除 prompt injection。
- 热度是 YouTube 内部启发式，不是跨来源的客观热榜。
- 整合非常保守，不做通用事件聚类；无法确认同一事件就分开，可能漏合并。
- `(source, external_id)` 全局唯一，一个 Item 只归属一个 Topic，暂无多 Topic 关联。
- 没有分页、持久化队列、跨进程锁、断线进度恢复、开机自启或休眠恢复。
- 没有 Embedding、Vector DB、RAG 或新 AI Agent 框架。

后续优先根据实际使用反馈改进可靠性、人工复核体验与分页，不将以上未实现功能标为完成。
