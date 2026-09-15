# Changelog

## [Unreleased]

### Changed

- 文档与界面改为中文为主，保留技术名称、命令、字段及 API contract。
- 统一操作、状态与错误提示；保留原始内容和 AI 输出，不修改业务流程。

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
