# Changelog

## [Unreleased]

### Added

- 采集 Item（连同 AI 分析）与 Digest 支持移入回收站、恢复和永久删除；新增回收站页面与 API。
- Alembic `0005_content_recycle_bin.py` 增加 nullable `deleted_at` 和索引，保留已有数据。

### Changed

- 默认列表、Dashboard、AI 分析及 Digest 输入排除回收站内容；软删除 Item 保留来源唯一约束，避免重新扫描后自动出现。
- 永久删除仅允许操作回收站内容，前端二次确认；删除整个 Topic 的确认明确提示其回收站内容也会永久删除。

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
