# API 设计

接口路径、request / response JSON 字段及 HTTP status code 保持英文。Swagger：http://127.0.0.1:8000/docs。
后端错误继续使用 `{"detail":"..."}`；中文界面对已知错误进行展示层映射，不改变 API contract。

## GET /api/dashboard

只读概览，返回 total_topics、enabled_topics、total_items、relevant_items（已分析且相关）、unanalyzed_items、recent_items 和 recent_digests。近期列表最多 5 条，按时间及 ID 倒序，包含展示用 Topic 名称；第一份 Digest 为最新简报。不使用 activity 表或缓存计数，无新 migration。数据库不可用返回安全的 503。

## GET /api/status

保留 name、version、status，并提供 database、ollama、scheduler、notifications。Ollama 状态仅检查 API 是否可访问，不保证配置模型已安装；scheduler 反映实际启动状态，notifications 反映开关配置。不返回 Key、密码或连接字符串。

## Topic 管理

`GET /api/topics`、`POST /api/topics`、`GET /api/topics/{topic_id}`、`PUT /api/topics/{topic_id}`、`DELETE /api/topics/{topic_id}` 保持既有 contract。字段为 id、name、description、enabled；name 不允许为空，description 可为 null。

## POST /api/topics/{topic_id}/scan

无 request body，同步执行。默认使用 Topic.name 搜索 YouTube，一次最多 15 条，无分页；`USE_MOCK_SOURCE=true` 使用固定 3 条模拟结果。成功返回 HTTP 200：

```json
{"topic_id": 1, "source": "youtube", "fetched": 15, "created": 12, "duplicates": 3}
```

数量表示本次标准化结果，而非 YouTube 总匹配数，满足 fetched = created + duplicates。重复真实扫描仍调用 YouTube 并消耗配额。已存在的 `(source, external_id)` 全局跳过，包括归属其他 Topic 的内容；不更新内容或改变归属。空结果返回零计数。

| HTTP status code | 含义 |
| --- | --- |
| 404 | Topic 不存在，不调用信息源 |
| 503 | 缺少 YOUTUBE_API_KEY，或数据库写入不可用 |
| 504 | YouTube 请求超时 |
| 502 | 上游 HTTP、网络或响应格式错误 |
| 422 | 路径参数无效 |

无自动重试。数据库写入使用单个事务，无效上游数据在写入前被拒绝。enabled 不限制手动扫描。

## GET /api/topics/{topic_id}/items

成功返回 HTTP 200 数组，无内容时为 `[]`，按 collected_at DESC、id DESC 排序。Topic 不存在返回 404，数据库失败返回 503。

每条 Item 包含 id、topic_id、source、external_id、title、url、author、published_at、snippet、collected_at；author、published_at、snippet 可为 null。还包含可为 null 的 ai_relevant、ai_relevance_score、ai_category、ai_summary、ai_analyzed_at。不提供分页、筛选或排序控制。

## POST /api/topics/{topic_id}/digest

无 request body，最多使用 20 条已分析且相关的 Item，返回已保存的完整 Digest：

```json
{"id":1,"topic_id":1,"title":"Topic Brief","summary":"AI-generated content...","item_count":3,"generated_at":"2026-09-15T12:00:00Z"}
```

Topic 不存在返回 404。无符合条件内容返回 409，不调用 AI。Provider 使用与分析相同的 502 / 503 / 504 语义；数据库失败返回安全的 503。每次成功手动请求保存新快照，无自动重试。

## GET /api/topics/{topic_id}/digests

返回完整 Digest 数组，按 generated_at DESC、id DESC 排序。已有 Topic 无历史返回 `[]`，Topic 不存在返回 404。无分页和独立详情接口，所有摘要均由 AI 生成。

## POST /api/items/{item_id}/analyze

无 request body。针对所属 Topic 分析已保存 Item，成功返回 HTTP 200 和包含 ai_* 的完整 Item。显式重复调用仅在校验成功后替换旧结果。

Item 不存在返回 404；模型配置缺失、Ollama 模型或接口不存在、本地服务不可连接、数据库失败返回 503；超时返回 504；结构化输出无效或上游失败返回 502。不暴露原始模型响应和 traceback。

Provider 结构化结果：

```json
{"relevant":true,"relevance_score":0.87,"category":"news","summary":"A short summary."}
```

relevant 为严格 boolean；relevance_score 必须有限且在 [0,1]；category 为 1–50 字符，summary 为 1–1000 字符。Prompt 要求 1–3 句，不接受额外字段。结果映射到持久化 ai_* 字段。

## POST /api/topics/{topic_id}/analyze?limit=10

无 request body。limit 范围 1–10，默认 10，无效值返回 422。仅按 ID 顺序选择 ai_analyzed_at=null 的 Item，Topic 不存在返回 404。

```json
{"topic_id":1,"processed":3,"relevant":2,"irrelevant":1,"failed":0}
```

processed 表示成功数，等于 relevant + irrelevant；failed 为 Provider 失败数，尝试数为 processed + failed。部分 Provider 失败仍返回 HTTP 200，failed 非零；可单条重试查看详细原因。之前成功的内容已经保存，不因后续失败撤销；数据库失败返回 503。批量接口同步执行，可能需要数分钟，没有自动重试或后台队列；Scheduler 是独立的调用方。
