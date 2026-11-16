# SignalRadar v0.2.0（本地候选版本）

SignalRadar 是面向 Windows 单用户本地运行的个人信息情报工具。用自然语言描述关注意图，设置包含与排除条件，再通过一键更新完成采集、规范化、主题匹配、事件识别、单事件简讯和中文综合简报。

本版本不创建发布 Tag。Task C 的实施与验收见 [阅读工作台记录](docs/development/task-c-reading-workspace.md)；此前记录保留为历史快照。

## 当前功能

- Task C 阅读工作台：事件 Brief 与历史版本、AI 综合简报 / 程序简讯集合 / 无更新报告、精准关注 / 开放发现，以及持久化运行阶段。
- Task B 事件识别：混合 Topic 匹配、有界事件候选检索、重复报道/实质更新/待复核区分，保留来源、冲突和持久化通知状态。
- Task A 单条规范化简讯：确定性文本清洗 → Topic 无关的事实提取 → 中文简讯与结构化字段，保留原文、版本及真实来源；既可独立手动触发，也可由新版一键更新 / Scheduler 有界执行。
- 中文 Dashboard、Topic 管理、内容筛选/排序、简报阅读及回收站。
- Topic 支持 name、description、逐条 include / exclude 规则、0～1 阈值（默认 0.80）、enabled。
- Query Builder 根据名称、描述与启用的包含条件提取关键词；内置 ChatGPT 模型、诺兰新电影简短模板，其他主题采用保守提取。最多 2 查询，不调用 AI 改写；不是通用自然语言翻译器。
- YouTube Data API / MockSource 将内容统一保存为 Item；实际执行查询与最近成功扫描时间可查看。
- Ollama 逐条输出符合度、理由、排除状态、分类和事实摘要。程序统一判定有效、无效、待复核、失败。
- YouTube 播放/点赞/评论等真实指标单独计算热度；MockSource 与缺失指标显示未知。
- 当前有效 TopicMatch 对应的 Event → Brief → Digest，保存事件、简讯版本及真实来源快照；旧版简报继续可读。单条 Item Analyze 作为高级独立操作保留，不是新版 Digest 的输入。
- 手动、一键更新和 Scheduler 复用同一逻辑；规则改变会使旧分析过期，不无条件进入新简报。
- 可选 Windows 通知、本地启动脚本、依赖状态、标准日志及默认关闭的 Ollama Trace。
- 单条 Item（连同 AI 结果）及 Digest 可移入回收站、恢复和二次确认永久删除。

## 技术栈与架构

Next.js + React + TypeScript + Tailwind CSS；Python + FastAPI；PostgreSQL + SQLAlchemy + Alembic；本地 Ollama。Scheduler 使用 Python 标准库，Windows 通知使用 WinRT，没有新 AI 框架或前端依赖。

```text
Scheduler / 一键更新
→ Topic / Query Builder → SourceAdapter → Raw Item
→ Text Preprocessing → NormalizedItem → TopicMatcher
→ Event / EventUpdate → Brief / BriefVersion
→ Digest（AI 综合 / 程序简讯集合 / 无更新报告）
→ PostgreSQL → 精准关注 / 开放发现 / Frontend
→ 持久化事件通知候选 → 可选 Windows Notification
```

项目采用 monorepo：`frontend/`、`backend/`、`docs/`。版本 **0.2.0**，Alembic head **0010**。

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

已有项目无需重建虚拟环境。升级前停止旧进程并备份数据库，应用到最新 head（本次新增 `0010_reading_workspace.py`）。迁移只增加字段和表；旧 Raw Item、AI 结果与 Digest 均保留，旧分析标为待重新确认。不要用降级来启动旧代码。

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
| EVENT_PROCESSING_ENABLED | true；新版一键更新/Scheduler 每轮最多处理3条待处理事件资料；显式 false 为仅采集调试模式，不伪报无更新 |
| DIGEST_MAX_EVENTS | 10；范围1～20，另有11KB AI 输入预算；超预算保留完整简讯集合 |
| SCHEDULER_ENABLED | false；是否自动更新 enabled Topic |
| SCAN_INTERVAL_MINUTES | 60；0.1～10080 分钟 |
| NOTIFICATIONS_ENABLED | false；Windows 通知开关 |

Trace：`backend/logs/ollama_trace.jsonl`。可能含私人 Topic、原文和模型回复，不能公开上传；关闭后不会自动删除历史文件。

## 日常使用

1. 创建 Topic，填写自然语言描述、包含/排除条件、阈值和启用状态。复杂规则与未知来源身份可能进入待复核。
2. 点击“一键更新”。新版每轮最多处理3条待处理记录，依次保存规范化、匹配、事件、简讯和报告；有积压时再次运行。刷新后可恢复最近一次实际运行阶段及统计，不显示虚构进度百分比。
3. 在“精准关注”阅读符合当前启用 Topic 规则的 Brief，可按最新、相关性、真实 YouTube 热度或事件更新排序，展开匹配理由。
4. 在“开放发现”浏览已采集事件库的不同主题、来源。该入口独立于精准过滤，不能当作全互联网推荐，不会修改 Topic 规则。
5. 在事件详情查看来源声称、时间线、重要进展及 Brief 历史。重复报道增加来源，不重新生成；重要事实/冲突产生新版本。手动“重新生成”可重试降级内容。
6. 阅读“综合简报”：多个有效 AI Brief 可生成 AI 综合简报；单条或模型失败显示程序简讯集合；成功检查但无新进展显示无更新报告。来源/数据库失败显示失败，不能当成“暂无新闻”。
7. 每个已收录 Event 的事实指纹作为覆盖记录；没有新重要进展不会再次进入自动简报。“重新综合当前主题”显式绕过覆盖，仍严格校验当前 TopicMatch。

旧单条 Analyze / ai_* 信息仍在高级操作中保留。它与 Task A/B/C 的事实规范化、TopicMatch 和事件流水线不是同一分析状态，不应混淆统计。模型符合度是估计值，不是客观概率、准确率或传播热度。

### 符合度与热度

符合度来自 AI 的语义判断；热度仅来自对应平台实际统计。YouTube 热度使用播放量每日速率的对数归一化，以及可用点赞率/评论率；缺失指标不补 0，发布时间或播放量未知则热度未知。低热度不影响有效性，不与其他 Source 横向比较。算法详见 [系统设计](docs/architecture/system-design.md)。

### 配额与能力边界

一次 Scan 最多 2 次 `search.list`（各 15 条）及 1 次批量 `videos.list(part=statistics)`，无分页、无自动网络重试。重复扫描也消耗配额；查询不是来源身份认证。实际配额以 Google Cloud Console 和官方文档为准：[search.list](https://developers.google.com/youtube/v3/docs/search/list)、[videos.list](https://developers.google.com/youtube/v3/docs/videos/list)。

仅获取视频 metadata 和统计，**未观看或理解完整视频，不下载视频、不抓字幕或全文**。网络/配额导致部分搜索或统计失败时，在已有发现的情况下保留 Raw Item 并返回 warnings；没有任何成功搜索则明确失败。

### MockSource、Scheduler 与通知

`USE_MOCK_SOURCE=true` 时每个 query 返回 3 条稳定模拟内容；2 查询可返回 6 条，改变查询可能产生新的模拟 ID。它不是正式来源，内容和本地链接不代表真实新闻。MockSource 不模拟 AI，默认分析仍需要本地 Ollama。

Scheduler 与手动更新复用 TopicUpdateService。默认 Scheduler 关闭；开启时使用单后端进程，不使用 reload 或多 worker。重复扫描复用规范化、匹配、事件和 Brief；仅新事件/重要增量生成可收录的内容。通知仍使用 Task B 持久化候选，重复来源不提醒，通知不依赖 Digest 成功；领取后中断可能漏发，不保证端到端 exactly-once。安全关闭：Ctrl+C → `SCHEDULER_ENABLED=false` → 重启。

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
- Digest 整合与 EventResolver 均保守；事件关系无法确认时待复核，不强行合并，可能漏合并。
- `(source, external_id)` 全局唯一，Raw Item 保留最初采集 Topic；Task B/C 的匹配与 Event 可关联多个 Topic。
- 没有分页、持久化任务队列、跨进程锁、自动断线续跑、开机自启或休眠恢复；已保存阶段可查看，重启后需主动重试。
- 没有 Embedding、Vector DB、RAG 或新 AI Agent 框架。

后续优先根据实际使用反馈改进可靠性、人工复核体验与分页，不将以上未实现功能标为完成。


## Task A：单条智能简讯

扫描得到 Item 后，在内容卡片的“AI 规范化简讯”点击“生成简讯”。已有同一原文/版本结果直接复用；“重新生成”显式产生新修订，旧记录保留。这是独立入口；新版一键更新也会复用已保存的规范化结果，继续匹配、事件识别和 Brief。

人物、机构、事件类型、事件日期、关键词、claims 与 warnings 随简讯保存。`reported` 只代表来源声称，当前不做官方核验或交叉验证，不允许模型标记 `officially_confirmed`。YouTube 明确为 metadata-only，不代表已观看视频；其他来源也只使用实际已有的 snippet。

新增 migration `0007_item_normalization.py`，升级前保留本机备份。规范化失败显示错误、可重试，不修改 Raw Item。详情与验收见 [Task A 记录](docs/development/task-a-normalization.md)。


## Task B：事件识别与增量更新

在 Item 简讯下点击“识别事件”，或访问 `/events` 查看事件、来源和更新历史。事件是多个报道共同关联的现实事件，不是关键词分类，也不表示已经证实。同一规范化结果可匹配多个 Topic；每个 Topic 规则指纹独立失效，不重新调用规范化模型。

确定性规则先检查主体—行为关系与明确字面条件，复杂自然语言交给 AI；来源身份无法核实时待复核。事件按实体索引/类型/时间选最多20候选，明确重复只增加来源；有可追溯新事实才创建 EventUpdate。冲突保留两边说法，不覆盖原事实、不升级官方确认。

自动使用时设置 `EVENT_PROCESSING_ENABLED=true` 并重启，再按需启用 Scheduler / NOTIFICATIONS_ENABLED。Task C 起该事件流水线默认开启、每轮最多3条；已有 .env 若显式 false 需自行改为 true。单条手动识别仍可用。通知先持久化领取再调用 Windows；失败或中断不自动重发，因此可能漏发，不能保证端到端 exactly-once。

可重复离线演示（Fake AI / Fake 通知，隔离数据库，不消耗 API 配额、不弹窗）：

```powershell
cd D:\Projects_ltl\Signal-Radar\backend
.\.venv\Scripts\python.exe scripts/demo_event_pipeline.py
```

预期：1个Event、3个来源、2条更新（初始事件+售价进展）、2次Fake通知，重复报道无通知。详见 [Task B 实施与验收](docs/development/task-b-events.md)。
