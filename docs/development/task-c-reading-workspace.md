# Task C：智能简讯、综合简报与双模式工作台

验收日期：2026-11-17。本次为 v0.2.0 开发分支，不创建 Release Tag、不合并 main。

## 仓库审计与实施计划

起点工作区干净，基线为 Task B 提交 `a8b3b858e060bf4a9515fe898b3a0caa20fdede6`，包含 Task A `cb38416`；本机 PostgreSQL head=0009。已核实 NormalizedItem、TopicMatcher、EventResolver、多来源/增量/冲突存储、事件通知候选、Scheduler、一键更新与 Ollama Trace 均存在。起点完整测试308通过。此前公共 Digest 仍读取单条 Item 的有效 ai_summary，缺少事件 Brief、阅读版本和独立发现信息流；事件附加阶段默认关闭，运行进度仅在当前响应中。

沿现有服务实施：新增 Brief / 版本 / 报告关联 → 事件流水线自动生成简讯 → ReportService 与三级结果 → 双模式 Feed → 阅读界面与持久化状态 → 保留 Scheduler / Task B 通知 → 测试、迁移、文档、真实模型分层验收。未增加依赖、来源、AI框架、后台队列或向量设施。

## 完成功能和兼容策略

- Raw Item → Text Preprocessing → NormalizedItem → TopicMatch → Event / EventUpdate → Brief → Report。主流程不重复执行旧 Item Analyze，原 API 与高级操作仍保留。
- Brief 一 Event 一记录，重要进展或冲突保留新版本，事实指纹复用避免重复生成；重复来源仍可在最新来源列表查看。
- Brief 来源为程序关联的真实 Item/URL/规范化版本；模型只能引用 fact_indices，不创造来源。unverified / conflicting 均不表示官方证实。
- 报告区分 AI `digest`、程序 `brief_collection`、`no_updates`；异常输出不保存为AI成功。部分采集故障、待处理积压或处理失败不伪报无新闻。
- TopicMatch 当前规则、最新规范化、原始删除状态和阈值统一控制精准关注及新报告；已覆盖无重要变化事件排除，显式force可重新综合。
- 开放发现只使用当前已有事件库，近期/跨主题覆盖、主要来源限额、稳定探索扰动、已读降权；与精准规则互不修改。
- 中文阅读入口、首页简讯优先、事件时间线/Brief版本、来源展开、报告结构和历史切换、实际运行阶段恢复。前端时间显示 Asia/Shanghai。
- 一键更新与Scheduler同服务；通知继续由Task B持久化候选派发。没有新重要事实不重新通知，Digest降级不阻止事件提醒。

旧 DigestService 的旧算法仍作为内部兼容路径与独立回归测试保留；公开生成路由已改为 ReportService，历史读取/回收站不改写旧内容。

## AI 输入、输出与稳定性

事件 Brief：system 明确外部数据不可信、不能执行指令、不增加未知事实，user 为 JSON 结构化Event事实/实体/实际来源摘要，coverage=limited_metadata；输出 title / summary / fact_indices。中文简讯通常100～250字，资料不足可短，不凑字数。

综合：只输入Topic名称/描述和通过当前规则的Brief（ID、Event、中文标题/正文、实体、核实状态），不再加入原始 snippet / YouTube description；输出 title / core_updates / events[{brief_id,text}] / watch_points。事件正文逐项绑定现有Brief，程序组装来源、事件跳转与版本快照。

请求继续 temperature=0、stream=false、HTTP format=JSON Schema；复用原始响应Trace、JSON容错和最多一次自动重试。校验包含严格Pydantic、中文、任务漂移迹象、数字证据、实体锚点、冲突保留、事实/简讯索引绑定。AI综合失败直接展示已保存Brief，无额外降级AI调用。程序降级明确标识，原始输出不泄露到页面。

这些是有界启发式，不能证明自然语言完全忠实，不能彻底杜绝prompt injection或幻觉。没有独立身份认证、事实核验或全文理解；多来源不自动升级可信度。

## 数据库迁移与备份

新增 `backend/migrations/versions/0010_reading_workspace.py`（down_revision=0009）。新增 briefs、brief_versions、digest_briefs、reading_runs、event_reads；digests仅增加类型/状态/错误/模型/统计字段，旧行标为legacy。已有 migration 未修改，历史数据不全量回填、不删除旧表。

迁移前正式库：topics=3、items=67、digests=6；规范化/事件等新流水线表为0。本机备份：`C:\Users\80538\AppData\Local\SignalRadar\backups\before-task-c-20261117-010810.dump`（72,814 bytes），已检查pg_restore TOC。备份、凭据及Trace不提交Git。

执行 upgrade head 后 current 为 **0010 (head)**，check 为 **No new upgrade operations detected.** 完整测试后复查：上述旧行数保持3/67/6；新Brief、事件、规范化及运行表均0。PostgreSQL集成测试写入使用外层回滚事务，离线演示和真实模型验收另用项目外隔离SQLite库。序列值可能被回滚测试消耗，不影响唯一性。

## 自动验收结果

| 检查 | 结果 |
| --- | --- |
| Task C前完整基线 | 308 passed |
| 最终完整后端（RUN_POSTGRES_TESTS=1） | **334 passed**，包括PostgreSQL集成；2条既有Starlette/httpx/anyio弃用警告 |
| 前端API测试 | **12 passed** |
| npm run lint | 通过 |
| npm run build | 通过，包含/focus和/discover |
| Alembic current / check | 0010 (head)，无模型差异 |
| git diff --check | 通过 |

所有pytest均使用 D:\pytest-temp 下新GUID --basetemp 与 -p no:cacheprovider。没有真实YouTube/Ollama网络调用或系统通知。原Task A/B、Topic、Item、回收站、AI、Scheduler/通知回归仍运行；旧测试按公开工作流的真实新语义调整，没有删除测试或降低覆盖。

新增覆盖：Brief生成/真实来源/索引校验/重复复用/重要与冲突更新/历史保留/模型失败模板、有效匹配过滤、来源限制与已读、配置失效/回收站、报告去重/大小/时间范围/显式重综合、JSON失败和最多一次重试、网络失败与部分搜索故障不伪报无新闻、实际运行阶段、历史Digest/迁移以及PostgreSQL存储。

验收中修复的真实问题：回收站Item再次命中时统计不能调用其规范化读取；部分Source警告不能当作完整无更新；摘要日期按UTC→北京时间显示；无更新报告不误用“旧版无来源”提示；首页与Topic明确区分旧单条Analyze状态和新事件流水线。

## 离线HTTP与浏览器验收

脚本 `backend/scripts/demo_reading_workspace.py`，最终报告 `D:\pytest-temp\598ff1b9eee243a8bc4e0f2d8b9026e0\report.json`：

- 实际HTTP一键更新依次得到 digest、no_updates、brief_collection。
- 模拟Source网络错误最终status=failed，digest=null。
- 精准关注/开放发现各4条，Fake事件通知4次，重复没有增加；连接重建后数据仍可读。
- SQLite、Fake Source、Fake AI、Fake Notification；不改.env、不写正式库、不消耗YouTube配额、不弹窗。

浏览器实际操作了精准关注、已读后发现排序、来源/匹配理由、三类报告历史、事件时间线和Brief重生成后的版本1/2切换。刷新后可读取失败运行记录。760px窄窗文档宽745px、scrollWidth745px，无横向溢出；桌面双列卡片与侧导航正常。验收临时Tab/服务器已关闭，viewport已恢复；未操作用户其他页面。

## 真实模型与真实来源分层报告

单独启动本机Ollama，使用本机已安装 `deepseek-r1:8b` 标签（实际模型family以本机清单为准），从**模拟NVIDIA事件事实**调用真实 Brief / 综合模型：2条Brief均completed，1条综合报告result_kind=digest、generation_status=completed。保留未独立核验/模拟资料限制，未把它们当作真实新闻。

本机隔离验收报告：`D:\pytest-temp\f885a0c11e314e22ada1240ef2e19de1\report.json`；Trace位于同一目录，仅包含合成验收输入，不提交仓库。规范化/匹配阶段为Fake准备，**不是完整真实Source→Ollama端到端测试**。本次未请求真实YouTube，未验证实时时钟Scheduler+原生Windows弹窗；相应行为通过Fake依赖/既有自动测试验证。本次自行启动的Ollama测试服务已停止，未修改模型或本机.env。

## 使用与风险

当前事件阶段默认开启，已有.env中的显式false需用户主动修改。每轮最多3条待处理，Digest默认最多10事件、11KB输入预算。后台队列/多进程锁/自动断线续跑未实现；reading_runs恢复的是已保存事实，不是假称任务继续执行。

发现候选最多200个近期事件，报告从有界候选选择；尚未分页，不保证大库全量覆盖。主要来源配额不是来源可信度或独立性证明。Raw输入缺失、模型误判、保守待复核/漏合并和8B超时仍需人工检查。通知持久化领取后崩溃可能漏发，不能承诺exactly-once。

未实现新Source、全文/字幕抓取、Embedding、Vector DB、RAG、云部署、多用户或新通知渠道；未创建Tag、未合并main。

## 本次文件清单

- `CHANGELOG.md`
- `README.md`
- `backend/.env.example`
- `backend/app/ai/ollama.py`
- `backend/app/ai/provider.py`
- `backend/app/briefs/__init__.py`
- `backend/app/briefs/feed.py`
- `backend/app/briefs/models.py`
- `backend/app/briefs/prompts.py`
- `backend/app/briefs/reports.py`
- `backend/app/briefs/router.py`
- `backend/app/briefs/schemas.py`
- `backend/app/briefs/service.py`
- `backend/app/briefs/validation.py`
- `backend/app/digests/models.py`
- `backend/app/digests/router.py`
- `backend/app/digests/schemas.py`
- `backend/app/events/pipeline.py`
- `backend/app/events/read.py`
- `backend/app/main.py`
- `backend/app/workflows/locks.py`
- `backend/app/workflows/service.py`
- `backend/migrations/env.py`
- `backend/migrations/versions/0010_reading_workspace.py`
- `backend/scripts/demo_reading_workspace.py`
- `backend/tests/test_digests.py`
- `backend/tests/test_events.py`
- `backend/tests/test_items.py`
- `backend/tests/test_normalization.py`
- `backend/tests/test_notifications.py`
- `backend/tests/test_reading.py`
- `backend/tests/test_scheduler.py`
- `backend/tests/test_trash.py`
- `backend/tests/test_updates.py`
- `backend/tests/test_v020_pipeline.py`
- `docs/api/api-design.md`
- `docs/architecture/database-design.md`
- `docs/architecture/system-design.md`
- `docs/development/local-development.md`
- `docs/development/task-c-reading-workspace.md`
- `docs/product/PRD.md`
- `frontend/app/BriefCard.tsx`
- `frontend/app/DigestArticle.tsx`
- `frontend/app/Navigation.tsx`
- `frontend/app/ReadingFeed.tsx`
- `frontend/app/digests/page.tsx`
- `frontend/app/discover/page.tsx`
- `frontend/app/events/EventBriefPanel.tsx`
- `frontend/app/events/page.tsx`
- `frontend/app/focus/page.tsx`
- `frontend/app/page.tsx`
- `frontend/app/topics/SavedRunStatus.tsx`
- `frontend/app/topics/TopicContent.tsx`
- `frontend/app/topics/TopicList.tsx`
- `frontend/app/topics/UpdateStatus.tsx`
- `frontend/app/topics/api.ts`
- `frontend/tests/api.test.mjs`
