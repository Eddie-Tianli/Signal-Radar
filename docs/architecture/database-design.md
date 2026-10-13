# 数据库设计

## 已实现存储

PostgreSQL 通过 SQLAlchemy 保存 Topic、Item 和 Digest。Alembic `0001` 创建 topics，`0002_create_items.py` 创建 items，`0003_item_ai_analysis.py` 增加 nullable AI 字段，`0004_create_digests.py` 增加简报历史。`0005_content_recycle_bin.py` 为 items 和 digests 增加 deleted_at 与索引。当前 head 为 `0005`，已应用 migration 保持不变。

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
| ai_relevant | boolean | 分析前为 null |
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
| item_count | integer | 本次采用的内容数量（service 限制 1–10） |
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

不新增回收站表，不改变 Item 的全局唯一约束。回收站内容不进入默认列表、Dashboard 统计、AI 分析、Digest 输入或自动更新待处理列表。软删除 Digest 仍作为自动生成的时间水位，防止删除简报导致无变化重建。永久删除只允许已软删除行；永久删除 Item 后可被再次采集，永久删除 Digest 后不再保留其时间水位。

Digest 是独立快照，Item 删除不修改历史 Digest。Topic 的 ON DELETE CASCADE 仍会永久删除全部子记录，包括回收站内容。降级 0005 会丢失删除标记，让尚未永久删除的内容重新可见；不要在日常使用中降级。
