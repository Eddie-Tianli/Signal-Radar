# API 设计（v0.2.0）

Swagger：http://127.0.0.1:8000/docs。endpoint、JSON 字段及 HTTP status code 保留英文。既有 endpoint、主要字段和错误形状保留，v0.2.0 增加规则、分析解释、查询及来源字段。客户端不能假定响应没有额外字段。

错误为 `{"detail":"..."}`，前端映射友好中文；不返回 Key、密码、连接字符串、原始模型输出或 traceback。同 Topic 写操作（包括规则与回收站）进行中返回 409，读取仍可用。

## Topic 与规则

`GET /api/topics`、`POST /api/topics`（201）、`GET /api/topics/{topic_id}`、`PUT /api/topics/{topic_id}`、`DELETE /api/topics/{topic_id}`（204）。不存在返回 404，参数/配置不合法返回 422。

```json
{
  "name": "ChatGPT",
  "description": "搜集 OpenAI 官方发布的 ChatGPT 新模型名称、发布时间和能力变化。",
  "relevance_threshold": 0.80,
  "include_rules": [{"text": "与模型发布有关", "enabled": true}],
  "exclude_rules": [{"text": "主要讨论 GPT-5.6 的内容，仅提及作比较不算命中", "enabled": true}],
  "enabled": true
}
```

创建/编辑 name 1～200 字、description 最多 2000 字；阈值必须有限且在 [0,1]。每类最多 10 条规则，每条非空、最多 500 字。写入规则可附已有 id 以保留身份；不得使用其他 Topic 或类型的 ID，不接受重复 ID。新规则不指定 id。

响应在原字段上增加 relevance_threshold、include_rules / exclude_rules（含 id / topic_id / rule_type / text / enabled）、rule_warnings、last_queries、last_scan_at。旧 name / description 即使超过新写入长度仍可读取。直接包含/排除冲突返回 warning；复杂冲突由分析返回 review / uncertain。

旧 PUT 仍替换 name / description / enabled；未提供规则或阈值时保留已有新配置，显式传空数组清空对应规则。删除 Topic 会永久级联删除内容、规则、简报及回收站，无法恢复。

独立规则操作：

| Endpoint | 请求 / 响应 |
| --- | --- |
| `POST /api/topics/{topic_id}/rules` | `{rule_type,text,enabled}`；201 返回完整规则 |
| `PUT /api/topics/{topic_id}/rules/{rule_id}` | `{text,enabled}`；200 返回规则，类型不改变 |
| `DELETE /api/topics/{topic_id}/rules/{rule_id}` | 204 |

## POST /api/topics/{topic_id}/scan

无 body，同步使用 Query Builder；最多 2 查询，每查询 15 条 metadata，合并后最多 1 次批量 YouTube statistics 请求，无分页或自动网络重试。MockSource 每 query 3 条，无外部网络。

```json
{"topic_id":1,"source":"youtube","fetched":20,"created":15,"duplicates":5,"queries":["OpenAI ChatGPT new model official","OpenAI ChatGPT model announcement official"],"warnings":[]}
```

fetched 为本次标准化条目数，含跨查询重复，不是平台总匹配数；`fetched=created+duplicates`。数据库 `(source,external_id)` 全局唯一，跨 Topic 重复也跳过，暂不做多 Topic 关联。已有同 Topic 内容只刷新真实热度，不修改原文或重新分配归属。

实际尝试查询即使失败也保留在 last_queries；last_scan_at 为成功保存时间。首次搜索失败：缺 Key 503、超时 504、上游/网络/响应问题 502。已成功发现部分内容时后续搜索/热度失败则保存已发现 Raw Items，返回 warnings，热度未知，不伪造指标。数据库失败安全 503，enabled 不限制手动扫描。

## GET /api/topics/{topic_id}/items

返回未删除 Item 数组，默认 collected_at DESC、id DESC，无内容 `[]`，Topic 不存在 404。服务端无分页和筛选接口，前端本地筛选排序。

保留 id / topic_id / source / external_id / title / url / author / published_at / snippet / collected_at 和 ai_relevant / ai_relevance_score / ai_category / ai_summary / ai_analyzed_at。

新增 analysis_status、analysis_stale、analysis_fingerprint、relevance_reason、exclusion_status、exclusion_reason、analysis_error、popularity_score、popularity_metrics。原文可为空字段保持原行为；热度缺失为 null，统计中的缺失计数也为 null。

analysis_status：pending / valid / invalid / review / failed。配置指纹不同动态显示 pending（failed 优先保留失败状态）；旧分析仍可回看并标 analysis_stale，不进入新简报。ai_relevant 是程序有效性标记，不是模型 relevant 的自由判断。符合度为 AI 分数，热度为平台真实指标计算，两者不可混用。

## POST /api/items/{item_id}/analyze

无 body，读取所属 Topic 的当前规则，仅分析该 Item。成功 200 返回完整 Item；允许主动重分析，包括 invalid / review。已删除或不存在 404。Ollama 配置/模型/连接问题 503，超时 504，格式/校验失败 502；数据库 503。

Provider 内部结构化结果（不是新增 HTTP request body）：

```json
{"relevance_score":0.91,"relevance_reason":"主要讨论新模型发布。","exclusion_status":"not_excluded","exclusion_reason":"","category":"model_release","summary":"有信息提到模型发布，具体能力尚待核实。"}
```

为兼容 Provider 保留可选 relevant，但程序忽略它。score 有限且在 [0,1]，reason 非空最多 800 字，excluded / uncertain 必须给非空 exclusion_reason；category 1～50 字，summary 1～1000 字，拒绝额外字段。摘要按 Prompt 使用中文、只依赖实际 metadata，不声称理解完整视频。

程序统一判定：uncertain 或直接规则冲突 → review；excluded 或低于阈值 → invalid；not_excluded 且达阈值 → valid。失败保存 failed / analysis_error，不清除 Raw Item 与旧摘要，不误判 invalid；可重试。

## POST /api/topics/{topic_id}/analyze?limit=10

limit 1～10，默认 10；只处理未分析、失败或当前配置指纹过期的未删除 Item，顺序执行、逐条提交。

```json
{"topic_id":1,"processed":3,"relevant":1,"irrelevant":1,"review":1,"failed":0}
```

保留 relevant / irrelevant 名称以兼容调用方，语义分别为 valid / invalid；`processed=relevant+irrelevant+review`。failed 为失败尝试数，不计入 processed；部分失败仍 200，已完成结果保留。Topic 不存在 404。

## POST /api/topics/{topic_id}/digest

无 body，选择当前配置下 valid、达阈值、not_excluded、摘要非空且未删除的最多 15 条 Item，按符合度与时间选取、保守整合成最多 10 单元。无符合条件内容返回 409，绝不调用 AI；Topic 不存在 404。

```json
{"id":1,"topic_id":1,"title":"模型动态简报","summary":"核心动态……","item_count":1,"generated_at":"2026-10-14T01:00:00Z","sources":[{"item_id":12,"unit_id":"U1","title":"模型发布","source":"youtube","url":"https://www.youtube.com/watch?v=example","author":"Example","published_at":null}]}
```

AI 仍只返回 `{title,summary}`；sources 由程序生成并保存，模型不能编造链接。item_count 是实际纳入的原始 Item 数，未必等于整合单元数。旧简报 sources=null。Provider 与数据库错误语义沿用 Analyze。Digest JSON/语义失败最多重试一次，每次 180 秒；空白或明显漂移不保存。显式手动生成每次可保存新快照。

`GET /api/topics/{topic_id}/digests` 按 generated_at DESC、id DESC 返回未删除历史；已有 Topic 无历史为 `[]`，不存在 404。来源为快照，Item 删除后仍可追溯。

## POST /api/topics/{topic_id}/update

无 body，application/x-ndjson。沿用 stage=scan / analyze / digest / complete，status=running / completed / partial / failed，以及 completed_steps / counts / pending_remaining / digest / digest_skipped / error / failed_stage。

新增 review、queries、warnings。最多分析 20 条待处理/失败/过期 Item，与批量和 Scheduler 使用同一 policy。有效摘要事实集合或配置改变才自动生成 Digest；仅评分/分类浮动或重新分析相同事实不重复生成。

HTTP 200 只表示流开始，必须检查终态；Topic 不存在 404、正在处理 409。断线后状态未知，无永久队列/进度恢复，先刷新已保存数据。单条失败不撤销此前提交，503 可停止更多模型请求。

## Dashboard 与状态

`GET /api/dashboard` 保留 total_topics / enabled_topics / total_items / analyzed_items / relevant_items / unanalyzed_items / recent_items / recent_digests / topics。relevant_items 仅当前配置 valid；unanalyzed_items 包含 pending、failed 与过期分析；回收站不计入。

topics 增加 analysis_state / analysis_counts / last_analysis_at / last_queries / last_scan_at，保留 id / name / enabled / item_count / last_collected_at。近期列表最多 5 条，Digest 含来源快照。只读，无统计表。

`GET /api/status` 保留 name / version / status / database / ollama / scheduler / notifications。Ollama available 只表示服务可达，不保证模型可用；不返回任何凭据。

## 内容删除与回收站

| Endpoint | 行为 |
| --- | --- |
| `DELETE /api/items/{id}` | Item 与 AI 分析软删除，204；幂等 |
| `DELETE /api/digests/{id}` | 简报软删除，204 |
| `GET /api/trash` | `{items:[...],digests:[...]}`，原字段与 deleted_at，按删除时间倒序 |
| `POST /api/trash/items/{id}/restore` | 恢复，204 |
| `POST /api/trash/digests/{id}/restore` | 恢复，204 |
| `DELETE /api/trash/items/{id}` | 永久删除回收站 Item，204 |
| `DELETE /api/trash/digests/{id}` | 永久删除回收站简报，204 |

不存在 404；永久删除未进回收站记录 409；Topic 忙碌 409；数据库 503。恢复后若规则已变，分析仍为过期，不自动认定有效。软删除 Item 仍参与去重；永久删除后可再次采集。软删除 Digest 仍作为指纹水位；永久删除后可能重新生成。Topic 删除永久级联全部内容，前端确认不可替代备份。


当前模型调用参数：temperature=0、stream=false、num_ctx=24576；单条 Analyze 输出预算 8192 / HTTP 180 秒，无自动重试。Digest 预算 4096 / 8192、最多一次重试、各 180 秒。超长输入或输出校验失败有明确错误；JSON schema 仍由 format 传递，未改变 DigestResult 的 title / summary contract。


## Task A：单条信息规范化（独立 API，兼容既有接口）

- `GET /api/items/{item_id}/normalization`：返回当前输入/schema 最新修订；尚未处理返回 HTTP 200 + null，Item 不存在或在回收站返回404。读取不需要 Ollama。
- `POST /api/items/{item_id}/normalize`：复用已有成功结果，否则逐条调用 Provider；`?force=true` 显式重新生成并留存旧成功修订。
- `POST /api/topics/{topic_id}/normalize?limit=3`：顺序处理尚未完成的 Item，limit 1–10，默认3；已完成不调用模型，失败/中断可重试。返回 `{topic_id,processed,failed,reused}`；Ollama 不可用/超时停止后续调用。reused 为遍历到的已有成功条数，不表示整个 Topic 总量。

单条返回 id、item_id、schema_version、revision、input_fingerprint、normalization_status、headline、summary、entities、event_type、event_date、keywords、claims、warnings、source_reference、content_coverage、text_truncated、source_metadata、matching_text、model_name、normalized_at、error。claims.status 仅 reported/unconfirmed/conflicting/unknown；source_reference 由服务写入，不允许模型伪造来源。

状态：未处理 GET null；处理中 processing；完成 completed；失败 failed/error。模型输出字段缺失、类型错误、事实/语言检查失败返回安全502；服务不可用503；超时504；Topic 忙409；参数错误422。单条失败后 GET 可检查持久化状态。批量部分失败返回计数，不伪造成功。

同一单条输出 schema：`{headline,summary,entities,event_type,event_date,keywords,claims:[{text,status}],warnings}`。headline/summary 中文，summary 一般100–250字，信息不足可缩短，schema 上限1000字符防过长。event_date ISO YYYY-MM-DD 或null。示例与实际 Prompt 见 Task A 记录。没有改动既有 Analyze / Scan / Digest response contract。


## Task B：事件与匹配 API（增量接口，旧Analyze/Digest不变）

- `POST /api/items/{id}/resolve?topic_id=1&retry=false`：先复用/生成当前规范化结果，再匹配指定Topic并识别事件；省略topic_id时最多匹配50个enabled Topic。retry=true只重试uncertain/失败，成功关系不会重复生成Event/Update。正常UI只匹配当前Topic，减少模型调用。
- `POST /api/topics/{id}/resolve?limit=3`：逐条补充该Topic采集归属的旧内容，默认3、范围1–10；已完成缓存不占模型处理额度；uncertain保留待复核，需单条retry。
- `GET /api/items/{id}/event-processing`：当前规范化版本下的匹配和关系审计；未规范化为null，404表示Item不存在/已入回收站。complete只表示处理完成，不代表matched或已核实。
- `GET /api/events?topic_id=1&limit=50`：最近事件（最多100），按updated_at/id倒序，Topic筛选仅当前规则的有效匹配。
- `GET /api/events/{id}`：摘要、事件时间、事实状态、来源、增量历史、候选与判断理由、AI参与、通知记录。

单条resolve返回 `{item_id,normalized_item_id,matches,decision,notification_candidates}`。matches含match_status/relevance_score/matched_rules/exclusion_reason/match_reason/ai_used/processing_status；decision含relation/candidate_ids/event_id/reason/ai_used/evidence/attempts/processing_status。relation为new_event/duplicate_report/event_update/uncertain，不确定不强行关联。

事件列表字段：id/canonical_title/event_type/event_date/summary/primary_entities/event_status/created_at/updated_at/source_count/topics。详情新增facts/sources/updates/decisions/notifications；source_count按规范化原始URL去重，源文章多个规范化修订不虚增链接数。历史来源快照不因Raw永久删除而丢失。

匹配/关系服务不可用503、超时504、结构化核验失败502；原始Item不丢。Topic或全局事件忙409、参数422、不存在404。没有通知重发API，sending/failed不自动再发，防止未知结果重复弹窗。

一键更新NDJSON新增可选events阶段及event_mode/events_processed/event_relations/event_failed；开关false保留旧步骤。digest contract不变，Task C未实现。

ScanResult新增 item_ids（实际发现、含已存在的Item ID），旧字段保留，供跨Topic事件复用；不会复制Raw所属关系。Topic匹配结果新增topic_snapshot，Event详情topic_matches展示当时配置、规范化ID与stale，未匹配结果仍可从Item处理状态查看。


## Task C：事件简讯和阅读 API（当前）

既有 Topic / Item / Event / 旧 Analyze 与历史 Digest 接口保留。以下接口不调用新来源：

| Method / endpoint | 行为 |
| --- | --- |
| GET /api/events/{event_id}/brief | 最新简讯；Event 存在但没有简讯返回 null，不存在返回404 |
| POST /api/events/{event_id}/brief?force=false | 生成或复用；force=true 保留新版本并重试；忙碌409；模型失败返回明确 fallback，而非假装 AI 成功 |
| GET /api/events/{event_id}/brief-history | 新版本在前，含来源、事实、核实/生成状态、模型、已读状态 |
| GET /api/feed?mode=focus&topic_id=1&sort=latest&limit=20 | 精准关注；sort=latest/relevance/popularity/updated，limit 1～50 |
| GET /api/feed?mode=discover&limit=20 | 开放发现；不得同时传 topic_id（422），不修改 Topic 配置 |
| POST /api/briefs/{brief_id}/read | 将最新已完成版本标为已读；不存在404，processing返回409 |
| GET /api/topics/{topic_id}/reading-status | 最近一次持久化运行记录；没有运行返回 null，含active进程锁状态 |
| GET /api/reading-overview | recent_briefs / discovery / review_count / event_count / brief_count / scope，只读 |

`POST /api/topics/{topic_id}/digest` 现使用 ReportService，从当前有效 Brief 生成；保留旧响应字段，新增 result_kind、generation_status、generation_error、model_name、run_stats、briefs。可选参数 since / until（带时区 ISO datetime）、event_status=active/developing/closed、force=false。force=true 显式重新综合已覆盖事件，但不绕过 TopicMatch。范围倒置422，Topic不存在404，数据库故障503。

返回 result_kind=digest / brief_collection / no_updates；历史行 legacy。简讯集合是可读降级，不是 AI 综合成功；没有新内容时不调用模型。历史通过原 `GET /api/topics/{topic_id}/digests` 读取，回收站行为保留。

`POST /api/topics/{topic_id}/update` 继续 NDJSON；新增 normalize / match / events / brief 阶段，保留原有字段并增加 run_id / briefs_generated / brief_fallbacks。HTTP 流已开始后，失败在最终事件 status/error/failed_stage 中体现，不能只看 HTTP 200。scan成功但待处理/失败尚存时为partial，不能伪造 no_updates。运行统计只包括实际发现和处理的内容，已移入回收站的记录不重新分析。

Brief 的 facts/sources 由程序绑定，不接受模型自造来源。`sources` 为生成时快照，`current_sources` 为最新已收集来源；历史快照不随实时链接改变。Digest.briefs 固化对应版本；旧摘要字段仍可读，但新报告不再读取原始 snippet 或 legacy ai_summary 作为综合输入。
