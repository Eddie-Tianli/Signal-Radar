# Task A：信息规范化与单条中文简讯 — 实施与验收

日期：2026-11-16。仅本阶段，不创建 Release Tag，不自动合并 main。

## 原有架构与复用

开始时 main 工作区干净，基线 commit 5232314；origin 为 Eddie-Tianli/Signal-Radar。已有 Topic / Raw Item / Analyze / Digest、单进程 Topic 锁、一键更新、Scheduler / Notification、Ollama Trace 与 JSON 提取/一次重试。

已有 NormalizedItem 是来源字段标准化 Pydantic schema，不是事实提取记录。本任务使用独立 ItemNormalizationRecord，输入不含 Topic 配置，避免将相关性判断与事实规范化混淆。Raw Item 当前仍只有一个 Topic，不在本任务扩张多 Topic 关系；规范化结果本身不依赖 Topic，可供后续匹配复用。

基线自动测试 236 passed / 6 个需显式开启的 PostgreSQL 测试 skipped；最终开启 PostgreSQL 测试验证。既有 API response、AI Analyze/Digest Prompt、Scheduler 与来源逻辑保留；只给 AIProvider 添加可选 normalize 能力，共用现有 HTTP/Trace/校验重试通道。

## 实现与数据

TextPreprocessor 负责 HTML/实体、NFKC、换行/空白、纯排版、精确重复标题与独立署名/版权元数据。不得按关键词删新闻事实，不改 Raw Item。清洗完整 matching_text 保留；模型输入标题300/正文3500/作者200字符上限，记录截取与覆盖程度。

NormalizationService 负责准备输入、完整原文指纹、结果复用、状态、调用、再次校验与事务保存。input_fingerprint 包含原文/来源与清洗版本；schema_version=1。已有 completed 默认直接返回；显式 force 创建新 revision，旧成功记录保留。failed 和意外中断 processing 可重试同修订。处理中记录先提交，但正文只在整个输出通过校验后保存。

只新增表 item_normalizations（migration 0007），FK items.id ON DELETE CASCADE；唯一(item_id,schema_version,input_fingerprint,revision)。字段包括 headline/summary/entities/event_type/event_date/keywords/claims/warnings/model_name/normalization_status/normalized_at/schema_version，以及来源快照、覆盖、匹配文本、指纹与错误。批量最多10、默认3，按条执行，不将多篇资料一次发给模型。未接入默认自动流水线，不增加 Scheduler 模型调用。

## 实际 Prompt 与 schema

实际中文指令完整保存在 `backend/app/normalization/prompt.py` 的 NORMALIZATION_PROMPT；OllamaProvider 追加既有英文不可信数据/只输出 JSON 指令，按本机已有配置可加 /no_think 兼容提示。实际 user message 为 NormalizationInput 的 JSON，含 item_id/title/text/source/author/published_at/url/content_coverage/text_truncated/source_metadata，没有 Topic、规则、其他文章或推测来源。

Prompt 要求单条、中文、100–250字左右但资料少可短、保留声称归因与未知、不执行来源指令、不用发布时间补事件日期、不伪造来源。只通过 API format 传递 JSON Schema，不重复打印 schema 定义。

```json
{
  "headline": "中文标题",
  "summary": "中文单条简讯",
  "entities": ["人物或机构"],
  "event_type": "事件类型",
  "event_date": null,
  "keywords": ["关键词"],
  "claims": [{"text": "具体来源声称", "status": "reported"}],
  "warnings": []
}
```

Pydantic extra=forbid / strict 类型、长度与数组限制。claims 仅 reported/unconfirmed/conflicting/unknown，没有 officially_confirmed：目前没有官方证据访问/交叉核验，不允许模型自行升级核实状态。source_reference 是程序保存的真实 Item/URL，模型不能输出 source 字段或编造链接。

轻量检查中文、角色/任务漂移、来源 URL、无依据年份与事件日期、明确自称已核实。多日期不明确时日期置 null 并加 warnings；这不是全面事实验证，人物机构冲突主要仍由模型提醒。即使原文肯定语气，也应阅读为单一来源说法。

标准 JSON → code fence → 首个 object → Pydantic → 业务校验；最多一次 retry，temperature=0、stream=false、JSON Schema，180秒超时，8192输出预算。HTTP失败不无限重试。Trace stage=item_normalization，保留原始响应再解析，沿用脱敏和默认关闭。服务错误保存安全 failed/error，不把原始输出或 traceback 传前端。

## API 与 UI

- GET /api/items/{id}/normalization：尚未处理为200/null；当前结果包含来源与状态；不需要 Ollama。
- POST /api/items/{id}/normalize：默认复用；force=true 显式新修订。
- POST /api/topics/{id}/normalize?limit=3：逐条处理未完成内容，返回 processed/failed/reused。已有 completed 跳过，503/504停止后续模型调用。
- Item 在回收站/不存在404；Topic忙409；参数422；校验失败502；Ollama不可用503；超时504。

Item 卡片新增独立中文 AI 规范化简讯区，显示待处理/处理中/完成/失败可重试，正文、实体关键词、事件日期、claims 与 warnings、真实原文链接及模型版本。保持原始信息与原 AI Analysis 分区，不做全站重设计；已完成读取不调用模型。旧修订数据库保留，本阶段没有旧版本选择器。

## 迁移与备份

升级前本机私有备份：`C:\Users\80538\AppData\Local\SignalRadar\backups\before-task-a-20261116-234428.dump`，34,511 bytes；pg_restore --list 验证通过，旁有 revision / counts 元数据。升级前0006，升级后0007 (head)，alembic check 无差异。

原 Topic 3 / Item 67 / Digest 6；迁移不删除、修改旧表字段或旧内容。0001–0006 不改。测试覆盖旧数据库升级保留、check、0007降级回0006再升级；降级会删简讯表，不作为普通运行操作。PostgreSQL 规范化测试使用外层事务回滚，不写正式测试行。

## 自动测试结果

- 最终完整后端（RUN_POSTGRES_TESTS=1）：**274 passed，2 warnings**。含真实 PostgreSQL roundtrip/时区/原文保护，新规范化32项。
- 既有 Analyze、Digest、Scheduler、回收站、Trace 全部回归通过。两条既有依赖弃用警告保留，不增依赖处理。
- 前端 npm run test:api：**10 passed**；npm run lint / npm run build：**通过**。
- Alembic：**0007 (head)** / **No new upgrade operations detected.**。
- pytest 每次使用 D:\pytest-temp 下新GUID与 -p no:cacheprovider --basetemp；未降低覆盖或删除用例。
- 本轮未追加浏览器点击验收；UI 完成 TypeScript生产构建与 API层验证，手动步骤见 Local Development。

覆盖清洗、原文保护、中文与字段提取、空事件日期/日期冲突、来源保守状态、来源追溯、YouTube metadata、JSON/fence/附加文字、一次重试/两次失败、不可用/超时、幂等/强制修订/失败重试、持久化、404/409/422/503、旧迁移兼容及原流程。

## 真实本机 Ollama 验收

服务原本未运行，本轮启动本机 Ollama 临时服务，未下载或更换模型。使用当前已配置 deepseek-r1:8b、本机 /no_think 兼容提示、实际 get_ai_provider 工厂，在临时 SQLite 保存明确标注为模拟的 Item，避免污染正式 Topic。

**成功：首轮一次请求，无重试，HTTP约91.15秒，done_reason=stop，eval_count=3468。Raw Item 未修改，结果保存后可读取。** 这是单条真实模型测试，不代表任意真实新闻均稳定，也不是事实核验能力证明。

输入：

```json
{
  "title": "Star River test announcement",
  "snippet": "这是用于本地验收的模拟公告，不是真实新闻。星河公司称其测试模型新增中文摘要功能，计划于2026年11月16日启用。具体效果尚未经过独立验证。"
}
```

实际模型输出（含程序补充的范围提醒）：

```json
{
  "headline": "星河公司测试公告",
  "summary": "这是一条用于本地验收的模拟公告，并非真实新闻。星河公司声称其测试模型新增了中文摘要功能，计划于2026年11月16日启用。具体效果尚未经过独立验证。",
  "entities": [
    "星河公司"
  ],
  "event_type": "公司声明",
  "event_date": "2026-11-16",
  "keywords": [
    "模拟公告",
    "测试模型",
    "中文摘要功能",
    "启用"
  ],
  "claims": [
    {
      "text": "星河公司声称其测试模型新增了中文摘要功能",
      "status": "unconfirmed"
    },
    {
      "text": "计划于2026年11月16日启用",
      "status": "unconfirmed"
    }
  ],
  "warnings": [
    "来源为模拟，内容未经独立验证",
    "仅整理单一来源声称，未访问官方证据或交叉核验；reported 不代表已证实。",
    "仅依据已获得的标题与 snippet，内容完整性未知。"
  ]
}
```

真实 Trace 与验收 DB 留在本机 `D:\pytest-temp\f408942b62fb46c8a4e5c5326cf6b061`，不提交或上传。临时服务验收后停止，不改变本机系统服务配置。

## 已知限制与范围

8B 模型仍可能误提取；中文/格式/年份检查是启发式，不是完整事实验证。只使用已有标题和 snippet；YouTube 绝不表示读取视频/字幕。模型名称变化默认仍可复用已有结果，切换模型后需 force 或提升 schema_version。

结果以 Item 而非 Topic 为单位，但当前 Raw Item 全局来源唯一且仅一个 Topic；未实现多 Topic 关联 UI。人物机构冲突、任意自然语言日期与全文事实证据仍有限。锁为单进程，未建立跨进程队列；并发请求同 Topic 返回409。没有 Event聚类、开放发现、跨事件综合 Brief/Digest、向量库/RAG、新来源或额外自动任务。

Git 功能分支：feat/item-normalization-v020。提交与推送结果以最终报告和实际远程提交为准，不自动合并 main，不创建 Tag。
