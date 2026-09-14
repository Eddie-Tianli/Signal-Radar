# Changelog

All notable changes to SignalRadar will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project follows semantic versioning where practical during early development.

## [Unreleased]

### Added

- Topic PostgreSQL persistence with SQLAlchemy, local environment configuration, and an initial Alembic migration. API contract unchanged.
- Isolated database-backed CRUD and migration tests.

### Validation

- Verified live PostgreSQL CRUD and persistence across backend process restarts on port `9912`.
- All 17 isolated automated tests pass; Alembic reports no schema drift.

### Planned (not implemented)

- Additional information sources.
- AI-powered relevance filtering and summarization.

> These are future plans, not completed changes or authorization to start the next development stage.

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
