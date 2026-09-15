# 数据库设计

## 已实现存储

PostgreSQL 通过 SQLAlchemy 保存 Topic、Item 和 Digest。Alembic `0001` 创建 topics，`0002_create_items.py` 创建 items，`0003_item_ai_analysis.py` 增加 nullable AI 字段，`0004_create_digests.py` 增加简报历史。当前 head 为 `0004`，已应用 migration 保持不变。

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
| item_count | integer | 本次采用的内容数量（service 限制 1–20） |
| generated_at | timestamp with time zone | 必填，数据库当前时间 |

历史按 `generated_at DESC, id DESC` 返回。简报为文本快照，没有 Item 关联表、embedding 或 event ID。0004 保留已有 Topic / Item；降级会删除简报历史。

## Migration 与测试命令

在 backend 中激活虚拟环境后执行：

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic check
python -m pytest -q
```

离线测试使用隔离 SQLite 文件，Item 测试启用 foreign key，覆盖 0001 → 0002 升级、降级及 Topic 保留。可选 PostgreSQL 测试验证真实约束及时区行为，不访问互联网。降级 0002 会删除 Item，不要在需要保留数据的数据库上执行。
