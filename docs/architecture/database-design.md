# 数据库设计

## 已实现存储

PostgreSQL 通过 SQLAlchemy 保存 Topic、Item 和 Digest。Alembic `0001` 创建 topics，`0002_create_items.py` 创建 items，`0003_item_ai_analysis.py` 增加 nullable AI 字段，`0004_create_digests.py` 增加简报历史。`0005_content_recycle_bin.py` 为 items 和 digests 增加 deleted_at 与索引。`0006_intent_pipeline.py` 增加自然语言规则和分析流水线字段。当前 head 为 `0010`，已应用 migration 保持不变。

## topics

| 字段 | PostgreSQL 类型 | 约束说明 |
| --- | --- | --- |
| id | integer / serial | 数据库生成的 primary key |
| name | text | 必填；应用拒绝空名称 |
| description | text | 可为 null |
| enabled | boolean | 必填，默认 true |

## items

```text
Topic 1 ─── N Item
```

一个 Topic 拥有多个 Item，每个 Item 必须关联已有 Topic。

| 字段 | PostgreSQL 类型 | 约束说明 |
| --- | --- | --- |
| id | integer / serial | 数据库生成的 primary key |
| topic_id | integer | NOT NULL，foreign key，已建索引 |
| source | varchar(100) | NOT NULL，稳定的来源命名空间 |
| external_id | varchar(500) | NOT NULL，来源内稳定标识 |
| title | text | NOT NULL；schema/service 拒绝空字符串及纯空白 |
| url | text | NOT NULL；schema/service 拒绝空字符串及纯空白 |
| author | text | 可为 null |
| published_at | timestamp with time zone | 可为 null；输入必须包含时区 |
| snippet | text | 可为 null |
| collected_at | timestamp with time zone | NOT NULL；数据库生成当前时间 |
| ai_relevant | boolean | 分析前为 null；新流程为程序有效性标记 |
| ai_relevance_score | double precision | 可为 null；CHECK 限制在 0 到 1 |
| ai_category | varchar(50) | 可为 null；简短分类 |
| ai_summary | text | 可为 null；AI 短摘要 |
| ai_analyzed_at | timestamp with time zone | 可为 null；分析成功时间 |

`fk_items_topic_id_topics` 拒绝不存在的 Topic，并使用 `ON DELETE CASCADE`。`TopicRecord.items` 与 `ItemRecord.topic` 使用 back_populates；passive ORM 删除将级联交给数据库。`ix_items_topic_id` 支持按 Topic 查询。

`uq_items_source_external_id` 保证 `(source, external_id)` 全局唯一，包括跨 session 写入。ItemService 对被拒绝的普通创建回滚并抛出 IntegrityError，不静默更新；扫描则仅对该身份冲突使用 ON CONFLICT DO NOTHING。

同一外部内容不能再次保存到另一个 Topic。多 Topic 归属需要未来单独设计关联模型。source 和 external_id 必须稳定；feed 内局部 ID 可能需要包含 feed 身份。这不是语义去重。

空字符串由 Pydantic 和 ItemService 校验，直接 SQL 会绕过应用规则，但仍受 NOT NULL、foreign key 和 unique constraint 约束。`ck_items_ai_score` 限制评分范围。已有行在分析前保持 AI 字段为 null，不包含平台专属 column。降级 0003 会删除 AI 字段和结果，保留原始 Item。

## digests

```text
Topic 1 ─── N Digest
```

Digest 必须关联已有 Topic。删除 Topic 时级联删除其 Digest，与 Item 行为一致。

| 字段 | PostgreSQL 类型 | 约束说明 |
| --- | --- | --- |
| id | integer / serial | primary key |
| topic_id | integer | 必填 foreign key，已建索引 |
| title | varchar(200) | 必填 |
| summary | text | 必填，由 AI 生成 |
| item_count | integer | 本次采用的原始 Item 数量（最多 15 条，整合为最多 10 单元） |
| generated_at | timestamp with time zone | 必填，service 记录生成完成时的 UTC 时间；数据库保留默认值 |

历史按 `generated_at DESC, id DESC` 返回。简报为文本快照，没有 Item 关联表、embedding 或 event ID。0004 保留已有 Topic / Item；降级会删除简报历史。

## Migration 与测试命令

在 backend 中激活虚拟环境后执行：

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic check
$testTempRoot = 'D:\pytest-temp'
New-Item -ItemType Directory -Path $testTempRoot -Force | Out-Null
$testTempPath = Join-Path $testTempRoot ([guid]::NewGuid().ToString('N'))
python -m pytest -q -p no:cacheprovider --basetemp $testTempPath
```

离线测试使用隔离 SQLite 文件，Item 测试启用 foreign key，覆盖 0001 → 0002 升级、降级及 Topic 保留。可选 PostgreSQL 测试验证真实约束及时区行为，不访问互联网。降级 0002 会删除 Item，不要在需要保留数据的数据库上执行。


## 回收站（0005）

`items.deleted_at` 和 `digests.deleted_at` 为 nullable `timestamp with time zone`，分别建立 `ix_items_deleted_at` 和 `ix_digests_deleted_at`。null 表示正常记录，非 null 表示软删除 UTC 时间。已有数据保持 null；恢复只清除此标记，保留原 ID、原文、分析结果及时间。

不新增回收站表，不改变 Item 的全局唯一约束。回收站内容不进入默认列表、Dashboard 统计、AI 分析、Digest 输入或自动更新待处理列表。软删除 Digest 仍作为自动生成的指纹水位，防止删除简报导致无变化重建。永久删除只允许已软删除行；永久删除 Item 后可被再次采集，永久删除 Digest 后不再保留其输入指纹水位。

Digest 是独立快照，Item 删除不修改历史 Digest。Topic 的 ON DELETE CASCADE 仍会永久删除全部子记录，包括回收站内容。降级 0005 会丢失删除标记，让尚未永久删除的内容重新可见；不要在日常使用中降级。


## 自然语言检索与可检查分析（0006）

只增加字段与 `topic_rules` 表，不删除任何旧列、Raw Item、AI 结果或历史 Digest。

### topics 增量字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| relevance_threshold | double precision NOT NULL DEFAULT 0.80 | CHECK 在 [0,1]，阈值由程序应用 |
| last_queries | JSON nullable | 最近一次实际尝试的搜索词，包含失败的尝试 |
| last_scan_at | timestamptz nullable | 最近成功保存采集结果的 UTC 时间 |

### topic_rules（Topic 1:N Rule）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | integer primary key | 后端生成稳定 ID |
| topic_id | integer foreign key / index | topics.id，ON DELETE CASCADE |
| rule_type | varchar(10) NOT NULL | CHECK include / exclude |
| text | text NOT NULL | 应用拒绝空白，最多 500 字 |
| enabled | boolean NOT NULL DEFAULT true | 是否参与分析与配置指纹 |

应用限制每类最多 10 条，支持逐条 API 或 Topic 保存时批量同步；不使用大 JSON 替代规则独立操作。旧客户端 PUT 未提供规则/阈值时保留新配置。Topic 删除仍级联删除规则和内容。

### items 增量字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| analysis_status | varchar(20) NOT NULL DEFAULT pending | CHECK pending / valid / invalid / review / failed |
| analysis_fingerprint | varchar(64) nullable | name、description、启用规则、阈值及 policy 版本的 SHA-256 |
| relevance_reason | text nullable | AI 符合度理由 |
| exclusion_status | varchar(20) nullable | CHECK excluded / not_excluded / uncertain |
| exclusion_reason | text nullable | 排除或待复核理由 |
| analysis_error | text nullable | 安全的本地错误说明，无原始响应或 secret |
| popularity_score | double precision nullable | CHECK [0,1]，YouTube 程序计算，不是 AI 分数 |
| popularity_metrics | JSON nullable | 真实 viewCount / likeCount / commentCount、retrieved_at、algorithm |

复用 `ai_relevance_score`、`ai_summary` 等字段，不新增重复的 relevance_score / analysis_summary。旧 AI 结果迁移后保留，但默认 pending 且指纹为空，不纳入新简报，需重新分析。配置变化后 API 动态返回 analysis_status=pending 和 analysis_stale=true，数据库保留旧结果以便查看；failed 不等于 invalid。

### digests 增量字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| sources | JSON nullable | 每个来源的 item_id / unit_id / title / source / url / author / published_at 快照 |
| input_fingerprint | varchar(64) nullable | 配置及实际有效事实集合的 SHA-256，避免自动生成重复快照 |

sources 是快照而非强制 Item foreign key，因此手动删除 Item 后仍可核对原来源；旧 Digest 保持 sources=null 并在界面说明。小规模只读快照与统计采用可移植 JSON，当前无需 JSONB 查询或 GIN 索引。热度和仅评分/分类浮动不触发新简报，配置或有效事实集合改变才更新。

迁移前用 pg_dump custom format 备份并校验可列出目录。0006 仅 ALTER ADD COLUMN / CREATE TABLE / CHECK，不重建 Topic 父表，避免 SQLite 测试中的级联误删。生产升级是 PostgreSQL 事务性 DDL。降级会丢失规则、理由、热度及来源快照，不是正常恢复操作；恢复备份需明确确认覆盖目标，不能盲目执行。

分析失败仅更新失败状态与安全错误，不将 analysis_fingerprint 改成新规则指纹；已有摘要与上次成功时间保留为历史。API 按当前配置计算 analysis_stale，failed 不被伪装为 invalid 或成功。


## Task A / migration 0007：item_normalizations（已实现）

`Item 1:N ItemNormalizationRecord`，表为 `item_normalizations`，FK item_id → items.id ON DELETE CASCADE。Topic 不进入规范化主键或输入，一次单条结果可独立用于后续 Topic 语义匹配；不改变当前 Item 所属 Topic 的设计。

| 字段 | 类型 / 说明 |
| --- | --- |
| id / item_id | integer PK / FK，item_id 索引 |
| schema_version / input_fingerprint / revision | varchar(20) / varchar(64) / integer |
| normalization_status | varchar(20)，CHECK processing / completed / failed |
| headline / summary | nullable text；未成功时为空 |
| entities / keywords / claims | nullable JSON，claims 为 text + status |
| event_type / event_date | nullable varchar(80) / date，事件时间不等于 published_at |
| warnings | JSON，模型提醒加程序覆盖/核验范围说明 |
| source_reference | JSON，程序生成的真实 item_id/url/source/author/published_at 快照 |
| content_coverage / text_truncated | varchar(30) / boolean |
| source_metadata / matching_text | JSON / text，署名版权等与清洗后的匹配文本 |
| model_name / normalized_at / error | text / nullable timestamptz / nullable text |

唯一约束 `(item_id, schema_version, input_fingerprint, revision)`。fingerprint 包含完整 Raw Item 相关字段与清洗版本，不包含 Topic 或模型名；更换模型需显式 force。相同输入/schema 默认复用最新 completed；failed/中断 processing 重试同条记录。force=true 在完成结果之后新建修订，不覆盖旧成功记录。API 默认返回当前输入最新修订，旧修订保存在数据库，当前未提供前端版本历史选择器。

先提交 processing 标记，校验通过才一次保存所有结果字段和 completed；失败只写 failed/error，不存半成品。Topic 级单进程锁与既有删除/扫描协作，数据库唯一约束兜底；不声称跨进程分布式幂等。Raw Item 软删除时结果一起隐藏并可随恢复读取，永久删除/删除 Topic 会级联删除。

0007 只新增表，不回填/覆盖旧 Item、AI 或 Digest。升级前备份，旧 migration 保持原样。downgrade 0006 会删除规范化结果，日常不执行降级。


## Task B / migrations 0008–0009（当前 head 0009）

只新增表与nullable列/索引，不删除旧内容，不改0001–0007。新增：

| 表 | 关键内容 / 约束 |
| --- | --- |
| events | integer稳定PK、canonical_title、event_type/family、event_date、summary、primary_entities、facts、active/developing/closed、created/updated；identity_fingerprint唯一 |
| event_entities | event_id + entity_key复合PK，entity_key索引供候选检索 |
| event_sources | Event关联多个NormalizedItem；normalized_item_id唯一可空，删除原记录SET NULL，真实URL/Item快照与声称保留；url_key索引 |
| topic_matches | normalized_item_id/topic_id/config_fingerprint唯一；status/score/规则/排除理由/依据/AI参与/处理状态/错误 |
| event_decisions | normalized_item_id/resolver_version唯一；候选ID、最终关系、Event ID、依据、证据快照、AI参与、失败与重试审计 |
| event_updates | event_id/fact_fingerprint唯一；normalized_item_id可空、new_event/new_facts/conflict、new_facts、真实source_reference、importance与时间 |
| event_topics | event_id/topic_id/match_id唯一；支持多Topic，当前有效关联按配置指纹过滤，旧依据保留 |
| event_notifications | topic_id/event_id/event_update_id唯一；pending/sending/sent/failed/suppressed、原因、错误、sent_at，派发状态持久化 |

新增 items.canonical_url_hash nullable varchar(64)，唯一索引。新写入计算规范化URL指纹（保留身份fragment、去追踪参数）；旧值保持null，避免清理/合并历史行。对旧数据精确URL仍检查，未回填指纹的旧追踪参数变体可能需要后续维护；不删除旧重复项。source/external_id原唯一约束继续存在。

Raw Item仍有一个采集归属Topic；NormalizedItem通过topic_matches可用于多个Topic，Event通过event_topics共享，不复制规范化模型结果。Event不代表已核实事实。所有声称状态继续沿用Task A保守枚举，无officially_confirmed。

发送状态遵循持久化at-most-once尝试；sending在崩溃后表示结果未知，不自动重试。通知disabled时保留pending。永久删除Topic会删除其匹配/关联/通知，但保留共享Event与历史来源快照；永久删除Item使规范化FK置空，事件历史仍可追溯URL快照。

升级前本机备份，upgrade head/current/check；downgrade0007会丢失Task B表与URL指纹，仅用于隔离迁移测试，不用于日常操作。

0009 为 topic_matches 增加 nullable JSON topic_snapshot，保留当时的名称、描述、规则、阈值、别名与策略版本。旧记录允许null；新判断均保存快照，改规则后仍可解释历史。0008只建事件表，0009为增量字段，均不改写原有Raw/AI/Digest。


## Task C：Brief 与报告持久化（0010）

```text
Event 1 ── 1 Brief 1 ── N BriefVersion
Digest 1 ── N DigestBrief ── 1 BriefVersion
Topic 1 ── N ReadingRun
Event 1 ── 0..1 EventRead
```

`0010_reading_workspace.py` 为增量 migration，保留现有 Item、Event、EventUpdate、Digest 和回收站。新增：

| 表 | 主要字段和约束 |
| --- | --- |
| briefs | id PK、event_id UNIQUE FK events（CASCADE）、created_at timestamptz |
| brief_versions | id PK、brief_id FK、version，UNIQUE(brief_id, version)；content_fingerprint、last_update_id、title、summary、facts/sources/warnings JSON、verification_status、generation_status CHECK(processing/completed/fallback)、model_name、error、generated_at timestamptz |
| digest_briefs | digest_id FK（CASCADE）、brief_version_id / event_id FK（SET NULL）、coverage_fingerprint、snapshot JSON；UNIQUE(digest_id, event_id) |
| reading_runs | topic_id FK（CASCADE）、status、stage、stats JSON、error、report_id FK（SET NULL）、started_at / finished_at timestamptz |
| event_reads | event_id PK/FK、brief_version_id FK（SET NULL）、read_at timestamptz；记录已读版本，新版本重新视为未读 |

`digests` 增加 result_kind、generation_status、generation_error、model_name、run_stats JSON。旧行默认 result_kind=legacy，旧 title/summary/sources 不被重写；新行区分 digest / brief_collection / no_updates。item_count 仍表示实际来源 Item 数，事件数量从 briefs 快照获得，不改写旧含义。DigestBrief 固化事件、版本和来源内容，即使后来增加来源或重生成 Brief，历史报告仍可追溯。

Brief 的 verification_status 当前只有 unverified / conflicting，不能当作事实已核验。Brief.sources 是生成时快照，读取最新简讯可附 current_sources 显示新增报道；旧版本保持自己的来源快照。覆盖指纹用于报告增量选择，不将纯措辞重生成视为新事实。

迁移前停止写入并备份；本次本机已执行 pg_dump 自定义格式备份并检查 TOC，然后 upgrade head/current/check。数据库保存 UTC 时间，前端统一按 Asia/Shanghai 展示；SQLite 离线验收丢失时区的值按 UTC 解释。已有 migration 不改写，不通过降级删除历史来运行旧程序。
