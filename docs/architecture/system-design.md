# SignalRadar 系统架构

## 信息采集

```text
Topic
↓
Collection Service
↓
SourceAdapter (YouTubeSource / MockSource)
↓
Normalized Item
↓
PostgreSQL
```

SourceAdapter 隔离不同平台的数据格式，Item 是统一内部内容模型。
`POST /api/topics/{topic_id}/scan` 同步执行：CollectionService 检查 Topic，仅使用 `Topic.name` 作为 query，调用所选 SourceAdapter，再通过 ItemService 保存标准化内容。手动扫描不受 enabled 限制；自动任务仅处理启用的 Topic。

YouTubeSource 调用官方 `search.list` 一次，参数为 `part=snippet`、`type=video`、`maxResults=15` 和 API Key。不分页、不扩展关键词、不自动重试，HTTP 超时为 15 秒。所有结果在写入前完成校验；响应无效则扫描失败。标题、描述和频道名称中的 HTML 实体会被解码，不存储平台原始 JSON。

`USE_MOCK_SOURCE=true` 时使用 MockSource，根据 query 返回 3 条固定模拟内容，无网络调用。它仅用于本地开发和测试，不是真实信息源。

ItemService.insert_if_new 使用数据库 `ON CONFLICT (source, external_id) DO NOTHING`。只跳过这一身份冲突；其他数据库错误回滚整次扫描。成功返回 fetched、created、duplicates，满足 `fetched = created + duplicates`，同一响应中的重复项也计入 duplicates。唯一性为全局范围，已归属其他 Topic 的视频计为重复，不会重新分配。

`GET /api/topics/{topic_id}/items` 按 `collected_at DESC, id DESC` 返回，不提供分页或筛选。Topic 不存在返回 404；缺少 API Key 返回 503；上游超时返回 504；上游 HTTP、网络或数据错误返回 502。客户端不会收到原始上游响应、Key 或 traceback。

YOUTUBE_API_KEY 从进程环境或被 Git 忽略的 `backend/.env` 读取。直接使用 HTTPX，不使用 Google SDK。自动测试通过 MockTransport 和假 Key 模拟响应；PostgreSQL 测试回滚测试数据，不调用 YouTube。真实 YouTube 验证仅手动进行。

## 本地 Item 分析

```text
Item → AIProvider → OllamaProvider → DeepSeek 8B (configured local model)
     → Structured Analysis → PostgreSQL
```

AIProvider 接收 Topic name / description 以及 Item title / snippet / author / source。OllamaProvider 将这些作为不可信元数据发送到本地 `/api/chat`，在 format 中提供 Pydantic JSON schema，使用 `stream=false` 和 `temperature=0`。不抓取全文或访问内容 URL。

OLLAMA_MODEL 选择已安装模型，业务代码不硬编码模型名称。HTTP 客户端禁用代理和重定向，只接受本机回环 HTTP 地址，超时 120 秒，不自动重试。

AnalysisService 校验并保存结果及带时区的分析时间。手动单条分析可覆盖旧结果，但失败不会清除旧结果。Topic 批量分析最多选择 10 条未分析 Item，依次处理并逐条提交；Provider 失败的内容可重试。该同步接口没有后台执行或并发协调。分析仅依据元数据，是模型判断而非核实后的事实。Prompt 要求 1–3 句摘要；校验限制非空且最多 1000 字符。

## Digest 与本地 Scheduler

```text
Scheduler → Topic → Collection Service → Item → AI Analysis → Relevant Items
→ Digest Service → AIProvider → Digest → PostgreSQL → Frontend
```

DigestService 最多选择 20 条已分析且相关的 Item，按 `COALESCE(published_at, collected_at) DESC, id DESC` 排序。AI 输入包括 Topic name / description 和 Item title / source / author / published_at / ai_category / ai_relevance_score / ai_summary，不传原始 snippet 或全文。

独立 JSON schema 要求 title 和 summary。Prompt 要求优先总结重要新信息、合并明显重复、禁止补充未提供事实，并生成适中长度的 AI 简报。手动生成每次保存一份历史快照；无符合条件内容时返回 409，不调用 AI。

Scheduler 使用 Python `threading.Thread`、`Event.wait` 和进程级 `Lock`，由 FastAPI lifespan 管理，默认关闭；测试强制禁止后台启动。首次执行等待配置间隔，下一次间隔从上一轮完成后开始，不积累漏跑任务。单个 worker 顺序处理 Topic，每个 Topic 使用独立 session / provider context；处理前再次检查 enabled。

每轮先扫描，再分析最多 20 条待处理内容（包括此前遗留内容），已分析内容跳过。只有本轮至少分析出一条相关内容才自动生成 Digest。无新相关内容则跳过。

单个 Topic 失败不影响其他 Topic。日志只记录 ID、数量和安全状态，不输出异常正文或 secret。已成功分析的数据不会因后续失败回滚。若简报生成失败，可手动生成；没有持久化重试队列。停止信号阻止后续任务，当前 HTTP 请求完成或超时后线程退出。

启用时仅运行一个 Uvicorn 进程，不使用 `--reload`。进程内锁不保护多进程或手动请求；手动扫描、分析测试时应关闭 Scheduler，避免竞争。

## 本地运行与 Windows 通知

```text
Digest commit → NotificationService → WindowsNotificationService → Windows toast
```

通知要求本轮出现新相关内容且新 Digest 已保存。手动生成、无变化或失败任务不通知。`NOTIFICATIONS_ENABLED` 默认关闭，只控制通知发送。工厂或发送异常单独捕获，日志记录 Topic ID，不撤销业务写入或使任务失败。

Windows 通知使用固定 PowerShell 脚本和内置 WinRT ToastNotificationManager。Topic 文本通过 stdin JSON 传入，再用 XML 文本节点插入，不拼接 shell。PowerShell 隐藏运行，超时 10 秒；复用 Windows PowerShell 开始菜单身份，不修改注册表、服务或快捷方式。

需要交互式 Windows 会话。专注助手或通知设置可能抑制横幅；日志 sent 仅表示系统发送调用返回，不保证用户看到横幅。没有远程通知通道。

`start-signalradar.ps1` 检查依赖、构建 Next.js，再调用 Python local runtime。Uvicorn 单进程在前台运行且不 reload；Next.js 生产子进程绑定本机回环，日志汇入标准 logging。Ctrl+C 先让 FastAPI 停止 Scheduler，再清理自身启动的前端进程树。

日志每 2 MB 轮转，保留 3 份备份。启动器不会安装或启动 PostgreSQL / Ollama 服务，不注册自启、不阻止休眠，也不提供重启恢复。保持终端及 Windows 登录会话打开。状态探测使用 `SELECT 1` 和本地 Ollama tags，不进行推理；有超时限制且只返回安全状态。

## 中文展示边界

前端将按钮、状态、辅助标签及已知 API 错误映射为中文，不改变 endpoint、JSON 字段或后端响应。未知错误仅显示中文提示和 HTTP 状态，不直接展示原始 detail。用户输入、来源内容、AI 输出与技术标识保持原样；不修改 AI prompt。

尚未实现 RSS、Web Search、embedding、语义去重、事件聚类、全文抓取或远程通知。
