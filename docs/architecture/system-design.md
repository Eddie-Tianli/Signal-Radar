# SignalRadar 系统架构（v0.2.0）

```text
Scheduler / 一键更新 / 手动操作
↓
Topic (description / include_rules / exclude_rules / threshold)
↓
Query Builder → Collection Service → SourceAdapter (YouTubeSource / MockSource)
↓
Raw Item → PostgreSQL
↓
AIProvider → OllamaProvider → Structured Analysis
↓
统一 policy（valid / invalid / review / failed，配置指纹）
↓
有效摘要 → Conservative Consolidation → Information Units
↓
Digest Service → AIProvider → 中文 Final Digest + 程序来源快照
↓
PostgreSQL → Frontend
↓
可选 Windows Notification（仅自动任务且发现新有效内容、保存新 Digest）
```

## Topic 与配置指纹

独立 `topic_rules` 表使规则可单独操作，保持 SQL foreign key、稳定 ID 和 enabled；不把可编辑规则塞进不可操作的大 JSON。每类最多 10 条；Topic 全量保存可批量同步规则，旧 PUT 未传新规则字段时保留它们。

SHA-256 指纹包括 policy 版本、name、description、阈值及启用的规则文本（排序）。不包含 last_queries、扫描时间或 Topic enabled，避免无语义变化引起重复分析。规则内容、启用状态、描述、名称或阈值改变后，旧 ai_* 保留，但状态对外为 pending / analysis_stale；未重分析不能生成新 Digest。

相同包含/排除文本的直接冲突由程序提示并判 review；复杂语义冲突交给 AI 解释 uncertain，不假装实现完整规则推理器。

## Query Builder 与采集

确定性模板支持 ChatGPT 模型发布及诺兰新电影；一般主题提取少量关键词，无 AI 改写依赖，不是通用翻译器。search 查询与筛选规则分离，不将 exclude 简单写成负关键词。

一次 Scan 最多 2 次 YouTube `search.list(part=snippet,type=video,maxResults=15)` 和 1 次 `videos.list(part=statistics)`（最多 30 个唯一 ID），无分页或网络重试，HTTP 单次超时 15 秒。查询去重、结果按 `(source, external_id)` 去重后再批量获取统计。官方配额以 Console 为准：[search.list](https://developers.google.com/youtube/v3/docs/search/list)、[videos.list](https://developers.google.com/youtube/v3/docs/videos/list)。

last_queries 在每次调用前提交，记录实际尝试；last_scan_at 在成功保存发现结果后更新。首次搜索失败明确报错；已有发现而后续搜索/统计失败时保留 Raw Item、热度未知，返回 warnings。错误不暴露 Key 或原始上游响应。

ItemService 使用 ON CONFLICT DO NOTHING，不重复保存来源身份。再次扫描只刷新同 Topic Item 的真实热度，不修改原文或归属。全局唯一意味着同一内容暂时不能属于多个 Topic。

MockSource 每查询 3 条稳定模拟内容，无网络；不是正式信息源。所有内容最初 pending。Raw Item 不因低分、排除或分析失败删除；手动回收站/永久删除行为另行处理。

## AIProvider 与确定性判定

保留 AIProvider / OllamaProvider 架构。输入单条 Topic 描述/规则及 Item 发布时间、采集时间、分析时刻、title、snippet（最多 2000 字符并标记截断）、author、source；只有 metadata，没有视频全文或字幕。JSON 数据和 system 指令分离，全部来源内容不可信，不能执行其中命令。官方/粉丝身份没有证据时应 uncertain，不能以频道名称当身份认证。

模型给出 relevance_score / relevance_reason / exclusion_status / exclusion_reason / category / summary。结果经严格 Pydantic 校验；程序而非模型 relevant 布尔值决定最终状态：

- uncertain 或直接规则冲突 → review；
- excluded 或 score < Topic threshold → invalid；
- 其余 not_excluded 且 score >= threshold → valid；
- 调用/校验失败 → failed，可再次处理；
- 无分析或配置指纹不同 → pending。

ai_relevance_score / ai_summary / ai_category / ai_analyzed_at 复用旧字段；ai_relevant 现在是程序有效性布尔值，不增加含义重复的 relevance_score / analysis_summary 列。失败保留 Raw Item 与旧摘要，状态/错误明确标识，不作为有效结果。

单条模型请求 temperature=0、stream=false、JSON Schema，HTTP 180 秒、分析预算 8192，不自动重试。实际 Trace 发现新增分析任务在 2048 预算下 done_reason=length 且 content 为空，在 4096 下也出现耗尽，故采用 8192 上限，不把 thinking 当 JSON。Ollama 只允许本机回环 HTTP、禁用重定向与代理。

## YouTube 热度（youtube-v1）

只使用 API 真正返回的非负 viewCount、likeCount、commentCount 和 published_at，保存获取时间与算法版本。若发布时间或播放量未知，score=null；其他计数缺失则从加权计算中移除，绝不补 0。

```text
age_days = max((now - published_at) / 86400, 1)
V = min(log(1 + views / age_days) / log(1 + 100000), 1)
L = min((likes / max(views,1)) / 0.10, 1)      # likes 可用时
C = min((comments / max(views,1)) / 0.02, 1)   # comments 可用时
score = sum(weight * component) / sum(available_weights)
weights: V=0.7, L=0.2, C=0.1
```

发布时间在未来超过一天视为不可评分，少量时钟误差按最小一天处理。每日速率部分减少老视频累计量优势，但不能完全消除年龄、规模、刷量和不同统计口径偏差；不是客观热度概率，尤其不跨 Source 比较。低热度不影响 valid。

## 信息整合与 Digest

先从当前指纹、valid、ai_relevant=true、score 达阈值、not_excluded、摘要非空且未删除的 Item 中，按 score DESC NULLS LAST、COALESCE(published_at,collected_at) DESC、id DESC 选最多 15 条。

canonical URL 仅规范化 scheme/host、query 次序及追踪参数，保留身份 fragment；相同 URL 可合并。否则数字/版本一致、有效时间差不超过 2 天、中文标题主体及英文实词一致、标题规范化后至少 12 字符且相似度 >=0.94、摘要规范化后至少 20 字符且完全一致才归并；缺发布时间时要求规范化标题与摘要完全相同。使用完整组两两检查，避免相似链条跨事件合并。无法确认即独立，宁可漏合并。没有 Embedding 或新 AI 调用。

最多 10 信息单元，每个包含来源 ID / 标识 / 时间和摘要；保留所有原来源快照，摘要输入设长度上限。不同版本、否定动作或不同 SPA fragment 不得仅因标题相近而强行合并。该算法不是通用事件聚类。

Digest AI 仅负责组织信息，不重新评分，不传原始 snippet / description。TOPIC / ITEMS / ITEM 边界中的 JSON 转义尖括号，防止来源关闭边界。中文简报保留不确定性，不加入外部事实；来源列表由程序保存，引用只能使用已有 unit_id。

保留 `{title,summary}` 严格结构化输出；temperature=0、stream=false。JSON → code fence → 首个 JSON object 的容错解析与 Pydantic / 中文 / 漂移 / 来源编号校验，共用最多一次 retry，输出预算 4096 / 8192、每次超时 180 秒。Digest 指令已按真实循环复述问题精简为事实整理任务，summary 目标 200–600 字，不复述输出说明；schema 仅在 HTTP format 保留，不重复粘进 system。无有效资料不调用模型，空白、格式错误或明显漂移不保存。

Digest.sources 保存 Item ID、unit_id、title、source、URL、author、published_at 的快照，Item 删除后来源仍可追溯；旧简报为 null 并在 UI 提示。input_fingerprint 覆盖配置和实际整合事实，忽略仅评分/分类浮动及排序改变；只有输入改变才自动生成，显式重新分析得到相同结果不重复生成。软删除简报仍作为水位；永久删除后可再次生成。

## 一键更新、Scheduler 与互斥

TopicUpdateService 统一 Scan → 选择最多 20 条 pending / failed / 配置过期内容 → 顺序分析 → 有效性 → 整合 → 按输入变化生成 Digest。批量 Analyze 最多 10 条，同样复用 pending_condition / AnalysisService；单条允许主动重分析。

每条分析成功/失败状态独立提交；服务不可用/超时（503/504）停止本轮更多模型调用并跳过 Digest，其他失败不会撤销已完成数据。NDJSON 提供实际阶段、数量、review、queries 和 warnings，HTTP 200 只表示进度流开始。没有永久后台队列，断线进度不恢复。

Scheduler 默认关闭，FastAPI lifespan 按环境启动并关闭，用标准库单轮 job_lock 避免重叠；同 Topic 手动/自动/规则编辑/回收站写操作共用进程锁。单 Topic 异常不影响其他 Topic。没有新有效摘要不自动生成，通知失败不影响已保存简报。

## UI、Dashboard、日志与回收站

沿用中文浅色 Tailwind 系统，不增加组件库。规则编辑、阈值、实际查询、AI 符合度与真实热度分开展示；状态、原因、历史分析过期提示及排序可检查。Dashboard 有效/待分析计数使用同一配置指纹。Digest 正文与程序来源列表分区，不伪造模型引用。

标准 logging 不记录 secret 或完整正文；显式启用的 Ollama Trace 才记录实际请求、原始响应、解析/校验/重试细节，失败不改变业务结果。Trace 可能含私人内容，仅留本机。

Item / Digest deleted_at 继续支持回收站；未删除内容才参与默认读取、分析、统计和整合。软删除 Item 仍参与采集去重。删除整个 Topic 仍是包含回收站的不可恢复级联删除。


## 上下文和输出保护

Ollama num_ctx=24576，实际 system+user UTF-8 输入最多 15000 bytes，预留最多 8192 输出与模板开销；超限明确报错，不默默丢弃条件或 system。Digest 数据本身最多 10000 bytes，按优先级减少末尾信息单元；模型不接收重复的来源完整 URL/标题，完整来源仍保存在数据库快照。较大上下文需要本机 RAM/VRAM，推理速度依赖硬件。

分析输出做中文、指令/代码/角色标记和未支持年份等轻量检查；analysis_time 不是事件年份证据。成功分析指纹在失败时保留，旧摘要仍标历史；failed 可重试。Digest 拒绝 schema/输出说明回显、不存在的 U 编号和未提供 URL，失败不保存。所有检查均不是完整事实核验或完全防注入证明。


#### 模型兼容与边界

`OLLAMA_NO_THINK_HINT` 默认 false，可选在 system 前加 `/no_think`；这是兼容提示，不保证关闭 thinking，不影响同一结构化校验或最多一次 retry。当前本机模型标签与实际 family 不同，验收记录保留了真实观察。失败重分析保留上次成功的 analysis_fingerprint / summary，状态为 failed，API 同时可显示过期；不会把历史摘要当成当前规则的有效结果。

标题相似但摘要只差一个实体也可能是不同事件，因此非同 URL 合并要求规范化摘要完全一致，容忍的标题变化非常有限。这会漏合并，优先保证来源与事件不被错误混合。语言、来源引用及年份校验为启发式防护，不是完整事实验证或 prompt injection 的形式化保证。
