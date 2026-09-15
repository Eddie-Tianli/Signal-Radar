# Changelog

All notable changes to SignalRadar will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project follows semantic versioning where practical during early development.

## [Unreleased]

### Documentation

- Aligned architecture and database design with the implemented Item/SourceAdapter foundation and verified `0002` migration; no live sources are claimed.

- Clarified the Content Collection planning baseline in the PRD, architecture, database design, and README.
- Added proposed ADR-002 for a unified Item model instead of platform-specific content tables.

### Added

- Topic Digest model and migration 0004, structured generation from up to 20 analyzed relevant Items, history APIs and frontend controls.
- Default-off local sequential Scheduler with configurable interval, enabled-Topic selection, pending-only analysis, new-relevance Digest gate, overlap protection and sanitized logs.
- Fake-provider Digest/Scheduler tests and local PostgreSQL Digest persistence checks.
- Topic frontend single-Item and bounded batch AI analysis controls, per-Item errors, batch counts, and refreshed persisted results.
- Clearly labeled AI-generated summaries, relevance scores/categories/timestamps, and unanalyzed state beneath original Item metadata.
- Local AIProvider/OllamaProvider structured Item relevance and short-summary analysis, configured through environment variables.
- Migration 0003 with nullable AI result fields and database score-range constraint.
- Single-Item analysis and bounded sequential Topic analysis APIs, plus mocked provider/error tests and PostgreSQL persistence checks.
- Local/test-only MockSource selected by USE_MOCK_SOURCE=true, with deterministic normalized Items and repeat-scan deduplication; YouTube remains the default.
- Offline MockSource/API tests and a rollback-isolated local PostgreSQL scan check.
- Topic frontend manual Scan action with independent loading/error states and fetched/new/duplicate counts.
- Collected Item lists with empty/error states, safe original links, and automatic refresh after a successful scan.

- YouTubeSource using one official Data API v3 search.list request, normalized into Items, with environment-based API key and sanitized errors.
- Synchronous Topic scan API with atomic identity deduplication and fetched/created/duplicates counts, plus Topic Item reads ordered by collection time.
- Mocked YouTube HTTP/API tests and an opt-in PostgreSQL insert-conflict check; no real quota is consumed by automated tests.

- Topic PostgreSQL persistence with SQLAlchemy, local environment configuration, and an initial Alembic migration. API contract unchanged.
- Isolated database-backed CRUD and migration tests.
- Unified Item ORM and Pydantic models with the existing `0002` migration, global source/external-ID uniqueness, and Topic foreign key.
- Bidirectional Topic/Item relationship, internal ItemService creation and topic listing, and rollback after rejected duplicate writes.
- Minimal SourceAdapter contract returning NormalizedItem; a test-only fake validates the flow without network calls.
- Item and collection architecture/database documentation.

### Validation

- Verified live PostgreSQL CRUD and persistence across backend process restarts on port `9912`.
- The original PostgreSQL stage passed 17 isolated tests; the Item/collection foundation passes 37 offline tests, plus an opt-in PostgreSQL check.

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
