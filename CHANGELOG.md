# Changelog

## [Unreleased]

v0.2.0 本地候选版本；未创建发布 Tag。

### Added

- Topic 自然语言描述、独立包含/排除规则、启用状态和默认 0.80 阈值，直接规则冲突提示。
- 确定性 Query Builder、实际查询记录，最多 2 次搜索和 1 次批量 YouTube 真实统计请求。
- 可检查的符合度理由、排除状态/理由、有效性状态、配置指纹和规则变化后的历史分析失效。
- YouTube 程序热度计算与原始指标快照，缺失显示未知，不与 AI 分数混用。
- 保守信息整合、Digest 来源快照、事实输入指纹，原始内容和历史简报继续保留。
- 中文规则编辑、状态/符合度/热度/时间筛选排序、实际搜索词和简报来源阅读。
- Item 与 AI 分析、Digest 的回收站、恢复和二次确认永久删除。
- 增量 Alembic 0005 回收站和 0006 检索流水线，不删除旧字段或数据。

### Changed

- 手动、批量、一键更新和 Scheduler 共用判定及待处理策略，规则变化后需重新确认历史内容。
- Digest 从最多 15 条有效候选整合为最多 10 单元，并限制总输入规模，不直接使用原始 snippet。
- 根据真实 Trace 提高 Item 有界输出预算与超时，增加上下文上限，过长输入明确报错而非静默截断规则。
- 默认关闭的 OLLAMA_NO_THINK_HINT 模型兼容提示；不保证停止 thinking，不绕过验证。
- 精简 Digest 指令，移除 system 中重复的 schema，保留 HTTP format、结构化校验及最多一次重试。
- 默认列表、统计和自动处理排除回收站内容；软删除保留来源唯一约束。

### Fixed

- 无效、待复核、失败或旧规则分析不会被误用为有效 Digest 输入。
- 新规则下分析失败不会把历史摘要误标为当前结果；失败原因在刷新后仍可查看。
- 仅评分/分类浮动不重复生成自动简报；服务不可用/超时不在本轮重复调用 Digest。
- 防止丢弃 URL 身份 fragment，以及将不同版本、否定事件或相似但不同信息错误合并。
- 后续查询或统计失败时保留已发现原始内容，未知指标不伪造 0 分。
- 拒绝系统指令/schema 回显、代码/角色标记、非中文摘要、明显无来源年份及虚构来源引用。

## [0.1.1] - 2026-10-13

本地候选版本，待 PostgreSQL 和浏览器人工验收；未创建 Git tag 或发布。

### Added

- 一键更新接口与实时 NDJSON 步骤反馈，复用 Scheduler 编排。
- Topic 级操作互斥、阶段失败说明、部分完成及恢复处理。
- 专用简报阅读页、历史切换、主题搜索和内容状态筛选。
- 默认关闭的 Ollama 本地完整请求/响应 Trace，带凭据脱敏。
- 前端原生 Node API 测试及更新工作流后端测试。

### Changed

- 统一中文浅色工作台、青绿色设计 Tokens、侧边导航和阅读层级。
- Digest 仅使用最多 10 条已分析、相关且摘要非空内容，按评分和时间稳定排序。
- 独立操作收进高级入口，保留手动分析与原始内容访问。
- Windows 后端测试统一使用 D:\pytest-temp 下的新 GUID 目录并禁用缓存。

### Fixed

- 根据真实 Trace 中 thinking 耗尽输出预算的证据，提高 Digest 输出预算并明确空回复/超时错误。
- 防止失败后的分析数据丢失，允许再次更新恢复未生成的简报。
- 数据库不可用返回安全的 503 和中文提示，不暴露连接参数。
- 防止同一 Topic 的手动操作与 Scheduler 重复执行。
- 安全新闻中正常引用攻击短语不再仅因关键词被误拒绝。

## [0.1.0] - 2026-09-15

### Added

- PostgreSQL persistence for Topics, unified Items, AI analysis and Digest history.
- YouTube and local MockSource collection with identity deduplication.
- Ollama structured Item relevance and summary analysis, plus Topic Digests.
- Optional local Scheduler and Windows notifications after successful automatic Digests.
- Local launcher, dependency status checks and rotating logs.
- Dashboard counts, latest Digest and recent content, backed by a small read-only API.

### Changed

- Unified light UI with Dashboard/Topics navigation, consistent states and keyboard focus.
- Reorganized Topic content around the latest Digest, original Items and clearly labeled AI analysis.
- Updated local setup, limitations, acceptance documentation and product version to 0.1.0.

### Fixed

- Prevented notification failures from invalidating completed collection and Digest work.
- Isolated per-Item analysis errors and retained safe API error messages.

## [0.0.4] - 2026-09-08

### Added

- Topic CRUD API.
- Topic creation endpoint.
- Topic listing endpoint.
- Single-topic retrieval endpoint.
- Topic update endpoint.
- Topic deletion endpoint.
- Pydantic schemas for topic request and response validation.
- In-memory topic storage.
- Basic automated tests for topic operations and validation.
- Topic management frontend at `/topics`, with creation, editing, deletion, loading states, and error handling.
- Homepage navigation to Topic Management.

### Changed

- Backend structure was separated into clearer router, schema, and service responsibilities.
- Local CORS configuration permits Topic CRUD requests from `http://localhost:3000`.

### Validation

- Added handling for missing topics with HTTP 404 responses.
- Added validation for invalid topic names.

## [0.0.3] - 2026-09-07

### Added

- Frontend-to-backend HTTP connection.
- Backend status endpoint at `/api/status`.
- Frontend display of backend availability and API version.
- Basic frontend error handling when the backend is unavailable.
- CORS configuration for local frontend development.

## [0.0.2] - 2026-09-07

### Added

- Next.js frontend application.
- React and TypeScript frontend environment.
- Tailwind CSS configuration.
- ESLint configuration.
- Initial SignalRadar landing page.
- Local frontend development server.

## [0.0.1] - 2026-09-07

### Added

- Initial SignalRadar repository structure.
- FastAPI backend application.
- Uvicorn local development server.
- Initial backend status response.
- Automatic Swagger API documentation.
- Initial project README.
- Initial product and development documentation.
- Project changelog.
- Git ignore configuration.

### Documentation

- Added initial product requirements.
- Added system architecture documentation.
- Added API design documentation.
- Added local development documentation.
- Added initial architecture decision record for the technology stack.
