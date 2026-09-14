# SignalRadar

SignalRadar is a personal AI-powered multi-source information intelligence platform.

## Goal

SignalRadar collects publicly available information based on user-defined topics, then filters, deduplicates, clusters and summarizes the information into personal intelligence briefs.

## Current Status

Early development. The first Topic Management workflow is implemented.

Completed:

- FastAPI backend and Swagger documentation at `/docs`.
- Next.js frontend with React, TypeScript, Tailwind CSS, and ESLint.
- Frontend-to-backend status request at `/api/status`.
- Topic CRUD API at `/api/topics` with Pydantic validation and automated tests.
- Topic management page at `/topics`, including creation, editing, deletion, loading states, and error handling.

Topic storage now uses SQLAlchemy and local PostgreSQL. Configure the database account and apply the Alembic migration before using Topic APIs; see [backend setup](backend/README.md). Live PostgreSQL CRUD and persistence across backend process restarts have been verified. Information collection, search, AI, and authentication are not implemented.

The API metadata version remains `0.0.1`; the changelog tracks development milestones separately.

## Local Development

Run the backend in one PowerShell terminal:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m alembic upgrade head
uvicorn app.main:app --reload
```

Before migrating, complete the account and `.env` setup in [backend/README.md](backend/README.md).

Run the frontend in a second terminal, starting from the repository root:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 and select **Manage Topics**, or visit http://localhost:3000/topics directly. Backend documentation is available at http://127.0.0.1:8000/docs.

Run `python -m pytest -q` from `backend/` with the virtual environment activated. Run `npm run lint` and `npm run build` from `frontend/`.

## Planned Platforms

- Web
- Android
- iOS

## Planned Tech Stack

### Frontend

- Next.js
- React
- TypeScript

### Backend

- Python
- FastAPI

### Database

- PostgreSQL

### Infrastructure

- Git
- GitHub
- Docker
- GitHub Actions

## Project Structure

```text
signal-radar/
├── frontend/
├── backend/
├── docs/
├── README.md
└── CHANGELOG.md
```
