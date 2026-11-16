# Task B：事件识别、智能去重与增量更新 — 实施验收

日期：2026-11-17。仅Task B，不实施Task C，不自动合并main或创建Release Tag。

## A — 仓库审查

开始工作区干净，分支feat/item-normalization-v020，基线cb38416；远程同SHA。Task A已实现item_normalizations、结构化摘要/实体/事件日期/声称/来源、状态/指纹/修订、Ollama Trace与最多一次重试；数据库head0007。Topic已有自然语言描述、include/exclude规则与0.80阈值。旧一键更新与Scheduler共用TopicUpdateService，但无独立Event及持久化事件通知。

基线完整后端274 passed。基于该开发基线新建feat/event-resolution-v020，没有覆盖用户修改。复用Task A、既有AIProvider/Trace/Topic锁、Collection和Notification，不重做Digest。

## B — TopicMatcher

输入为Topic名称、描述、启用规则、阈值、有限内置别名与单条规范化结果。描述优先，名称不是唯一依据。明确的字面前缀（排除关键词：/禁止包含：/必须包含关键词：）才做硬性字符串判断，普通“主要讨论X”不会因字面提及直接排除。

简单无额外语义限制时，标题与声称必须有直接主体—行为关系；仅多个词共现不足以匹配。复杂关系或规则使用AI语义复核，身份无法核验时保守uncertain。程序最后执行阈值与排除优先，score不是校准概率。匹配结果、配置指纹、理由、AI参与和失败状态落库；0009保存名称/描述/规则/阈值/别名/策略版本快照，旧规则仍能解释。

规则变化只使匹配失效，不重做Topic无关的简讯。普通成功/不匹配结果复用，uncertain可显式retry=true；错误允许重试，不把失败当作确定不相关。

## C — 数据模型与迁移

- Event：程序integer PK、身份指纹、规范化标题/类型/family、事件日期、摘要、实体与事实、active/developing/closed、时间。
- EventSource：一个Event关联多个NormalizedItem；真实来源快照、规范化修订及声称，URL索引。
- TopicMatch / EventTopic：多Topic共享规范化结果和Event，历史匹配保留，当前关联按配置指纹筛选。
- EventDecision：候选ID、关系、依据、AI参与、规范化证据、处理状态和尝试记录。
- EventUpdate：new_event / new_facts / conflict，新增声称、来源、重要性与时间；event+fact指纹唯一。
- EventNotification：topic+event+update唯一，持久化pending/sending/sent/failed/suppressed和时间/错误。
- EventEntity：实体键索引，用于有界检索。

0008_event_resolution.py 新增上述表及items.canonical_url_hash（nullable唯一索引）；0009_topic_match_snapshot.py仅新增Topic配置快照，不修改已应用0008。旧0001–0007保持不变。

原始Item仍只有一个采集归属Topic，但ScanResult.item_ids携带已有发现，第二个Topic扫描同一URL时可复用已有Raw/简讯并完成自己的匹配，不复制Raw。显式单条resolve省略topic_id最多匹配50个enabled Topic。

迁移前备份：C:\Users\80538\AppData\Local\SignalRadar\backups\before-task-b-20261117-002106.dump，39,018 bytes，pg_restore --list验证成功；旁JSON记录revision与行数。升级前0007，最终0009 (head)，check无差异。Topic3 / Item67 / Digest6 / Normalization0保持；正式Event/Update/Notification仍0，演示未污染正式数据库，PG集成用外层事务回滚。

## D — EventResolver

使用索引实体子查询+类型family+时间窗口+SQL LIMIT，不加载全部历史Event。通常±7天，明确价格进展±90天，无日期回看最近90天updated_at；同URL可补找较旧候选，但URL本身不是同事件证据。最多20个，超限或多个可信候选时待复核，不强行挑选。

主体/行为/时间兼容且事实键一致→duplicate_report；同实体不同收购/发布、不同明确产品不合并。明确同产品新增价格可确定性增量，原文冲突状态单独保留。模糊唯一候选才做AI两边结构化事实比较（旧事实最多20条），confidence<0.85或未指明合法新增索引则uncertain；AI不能生成Event ID或编造事实。一般无可靠主体/事实/具体事件信息也待复核。

跨语言可由规范化中文结果或AI语义比较关联，不要求原文语言相同。当前别名和词法并非通用实体链接器；可能漏合并，不声称已解决完整事件聚类。

## E — 更新与通知

重复来源只增加EventSource，不新增EventUpdate。新事实/冲突追加，旧事实与来源保留；reported/unconfirmed不升级officially_confirmed。与Task A一样没有独立官方证据核验能力。冲突不自动发确定性通知。importance是估计，不是热度或核实概率，普通新增事实>=0.8才进入候选；新事件可进入候选。

候选与发送解耦，不依赖Digest成功。派发前重新检查当前Topic配置、enabled和来源是否未删除；不符合则suppressed。通知disabled保持pending。先原子领取并提交sending，再调用Windows；成功sent，异常failed，重启/重试不自动再发送sending/failed。此为at-most-once发送尝试，可能漏发，不保证端到端exactly-once。当前没有人工通知重发API。

同一Topic仍使用既有锁；跨Topic识别额外使用原采集归属Topic锁，避免与Task A规范化重入；全局单进程Event锁避免并发重复创建，数据库唯一约束兜底。仍不支持多worker或分布式队列。

## F — UI与兼容

新增/events事件列表和详情：标题、类型、时间、状态、链接来源数、关联Topic；详情有摘要、来源声称/不确定性、来源列表、增量历史、候选/判断依据、历史Topic配置和通知状态。Item简讯区域新增事件识别、重复/增量/待复核标签与依据。

EVENT_PROCESSING_ENABLED默认false，避免意外附加大量本地模型调用。开启后一键更新/Scheduler每轮最多3条事件，调用同一EventPipeline，原Analyze/Digest不重写。Task B开关开启时用事件候选通知，不额外再发旧Digest通知；关闭时保留旧流程，其通知不属于事件级幂等保证。

Raw永久删除后仍保留Event的来源快照；Topic删除移除自身关联/通知，但不删除共享Event，界面确认已说明。Event本轮没有删除/回收站管理功能。事实生成质量仍需人工复核。

## G — 自动验证与运行演示

| 检查 | 最终结果 |
| --- | --- |
| 完整后端含PostgreSQL | 308 passed，2 warnings |
| Task B专项 | 34 passed |
| 前端API | 11 passed |
| npm run lint | 通过 |
| npm run build | 通过，含/events静态页面 |
| Alembic current | 0009 (head) |
| Alembic check | No new upgrade operations detected. |

每次pytest使用D:\pytest-temp下新GUID与-p no:cacheprovider --basetemp。两条warning为既有Starlette/httpx与anyio弃用警告，无新依赖、无真实AI或YouTube配额、无原生通知。

覆盖首条创建、URL去重、不同URL/中英文重复、同实体不同事件/产品、新事实和冲突、uncertain不合并、跨Item/Topic复用、自然语言/字面规则/身份未知、阈值/排除优先、不相关不通知、重试与重连状态保留、Scheduler共用/幂等、跨Topic锁、迁移旧数据/Task A/Digest回归、真实PostgreSQL候选和状态落库。

阶段回归暴露并修复了PostgreSQL JSON整行DISTINCT错误，改成索引ID子查询；SQLite新增timestamp默认使用可跨数据库编译的func.now。旧迁移测试head更新，原有“两篇文章复用同URL”的夹具改为不同URL，测试保留。

离线真实HTTP接口演示命令：

```powershell
cd D:\Projects_ltl\Signal-Radar\backend
.\.venv\Scripts\python.exe scripts/demo_event_pipeline.py
```

实际运行结果（隔离SQLite、Fake AI、Fake Notification）：

```json
{"relations":["new_event","duplicate_report","event_update"],"events":1,"sources":3,"updates":2,"notifications":2}
```

通过FastAPI接口创建Topic、依次扫描三条模拟报道、生成简讯、匹配、建事件、重复关联、新增售价、查看来源历史；通知累计1→1→2。关闭/重连数据库后仍可读，PostgreSQL另做事务回滚集成测试。并未实际重启Windows PostgreSQL服务，不能将连接重开称作服务重启验收。

最近演示报告保存在本机 D:\pytest-temp\b7651ba843ef4eb9933807b85ccc08d0\report.json，不提交数据库/日志文件。本轮Ollama未运行，未重新启动模型；新语义能力使用MockTransport/Fake验证，没有真实8B质量验收，也没有弹真实Windows通知或做浏览器点击/视觉验收。

## 限制与后续边界

- 匹配是保守启发式+小模型，不是完整事件理解，误判/漏合并仍可能发生。名称、产品键、family、时间窗口和源资料质量影响召回。
- 没有来源身份认证，不自称官方确认。输入只有实际已获得metadata/snippet，不读取完整视频。
- Raw URL指纹不破坏性回填旧行；旧精确URL会检查，旧追踪参数变体在首次规范维护前可能仍产生额外Raw，但事件层继续独立去重。
- 原始归属仍单Topic；共享结果通过匹配/事件关联，非多Topic复制Raw。
- 失败/中断通知不自动重发，可能漏发；单进程运行，非分布式exactly-once。
- 规则变化后旧匹配无效，历史结果保留；uncertain需要显式重试或人工复核，没有自动强制合并。
- 没有Event手动合并/拆分、事件回收站、Task C正式Brief/Digest分离、开放发现、Embedding、Vector DB、RAG、新来源、云部署或多用户。

## Git与文件清单

功能分支feat/event-resolution-v020，基于Task A。最终Commit/Push信息以实际远程验证和完成报告为准，不自动合并main，不创建Tag。

### 新增

- `backend/app/events/__init__.py`
- `backend/app/events/identity.py`
- `backend/app/events/matcher.py`
- `backend/app/events/models.py`
- `backend/app/events/notifications.py`
- `backend/app/events/pipeline.py`
- `backend/app/events/prompts.py`
- `backend/app/events/read.py`
- `backend/app/events/resolver.py`
- `backend/app/events/router.py`
- `backend/app/events/schemas.py`
- `backend/migrations/versions/0008_event_resolution.py`
- `backend/migrations/versions/0009_topic_match_snapshot.py`
- `backend/scripts/demo_event_pipeline.py`
- `backend/tests/test_events.py`
- `frontend/app/events/page.tsx`
- `frontend/app/topics/ItemEvents.tsx`
- `docs/development/task-b-events.md`

### 修改

- `CHANGELOG.md`
- `README.md`
- `backend/.env.example`
- `backend/README.md`
- `backend/app/ai/ollama.py`
- `backend/app/ai/provider.py`
- `backend/app/collection/service.py`
- `backend/app/items/models.py`
- `backend/app/items/service.py`
- `backend/app/main.py`
- `backend/app/normalization/service.py`
- `backend/app/notifications/service.py`
- `backend/app/notifications/toast.ps1`
- `backend/app/scheduler/runner.py`
- `backend/app/workflows/service.py`
- `backend/migrations/env.py`
- `backend/tests/conftest.py`
- `backend/tests/test_items.py`
- `backend/tests/test_normalization.py`
- `backend/tests/test_trash.py`
- `docs/api/api-design.md`
- `docs/architecture/database-design.md`
- `docs/architecture/system-design.md`
- `docs/development/local-development.md`
- `docs/product/PRD.md`
- `frontend/app/Navigation.tsx`
- `frontend/app/topics/ItemList.tsx`
- `frontend/app/topics/ItemNormalization.tsx`
- `frontend/app/topics/UpdateStatus.tsx`
- `frontend/app/topics/api.ts`
- `frontend/app/topics/page.tsx`
- `frontend/tests/api.test.mjs`
