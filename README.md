# SignalRadar

SignalRadar is a personal AI-powered multi-source information intelligence platform.

## Goal

SignalRadar collects publicly available information based on user-defined topics, then filters, deduplicates, clusters and summarizes the information into personal intelligence briefs.

## Current Status

Early development. Topic Management and manual YouTube collection are implemented.

Completed:

- FastAPI backend and Swagger documentation at `/docs`.
- Next.js frontend with React, TypeScript, Tailwind CSS, and ESLint.
- Frontend-to-backend status request at `/api/status`.
- Topic CRUD API at `/api/topics` with Pydantic validation and automated tests.
- Topic management page at `/topics`, including creation, editing, deletion, loading states, and error handling.
- Per-Topic YouTube Scan button with fetched/new/duplicate counts and automatic Item list refresh.
- Collected Item display with source, author, publication time, snippet, and original links.
- Per-Item Analyze and Topic Analyze Unprocessed Items controls for local Ollama analysis, with independent errors, batch counts, and persisted AI results.
- AI Analysis sections show relevance, score, category, explicitly AI-generated summaries, and analysis time beneath original content.

Topic and Item storage use SQLAlchemy and local PostgreSQL. Configure the database account and apply the Alembic migrations before using Topic APIs; see [backend setup](backend/README.md). Real YouTube collection requires `YOUTUBE_API_KEY`; local tests can use MockSource. Local AI analysis requires Ollama and OLLAMA_MODEL; authentication is not implemented.

The API metadata version remains `0.0.1`; the changelog tracks development milestones separately.

Content Collection currently supports manual YouTube searches normalized into Items.
Topic Digests and an opt-in local Scheduler are implemented. RSS, Web Search,
Email/mobile notifications and final UI redesign remain unimplemented.

Windows local notifications are available as an opt-in feature after successful
automatic Digest generation with new relevant content. Notifications default off.

## Local Usage (Windows)

Start local PostgreSQL first, then Ollama (optional for browsing/collection), then
run `./start-signalradar.ps1` from PowerShell in the repository root. It checks the
environment, database/migrations, Ollama and ports, builds Next.js, and starts both
servers on loopback in one terminal. Keep that terminal open; Ctrl+C shuts down
the backend gracefully and stops its frontend child process. No services or system
settings are created or changed.

Use `./start-signalradar.ps1 -CheckOnly` to validate without starting servers, or
`-SkipBuild` to reuse an existing frontend build when code has not changed.
Ollama unavailability is a warning; AI actions need it later. PostgreSQL failure
blocks the launcher with a setup message. `/api/status` reports dependency states
without credentials. Runtime logs rotate in ignored `logs/signalradar.log`.

For automatic local use, configure `SCHEDULER_ENABLED=true` and optionally
`NOTIFICATIONS_ENABLED=true` in backend/.env. Windows notifications require a
logged-in desktop session and allowed Windows PowerShell notifications. The banner
contains SignalRadar and the Topic; Windows may group it under Windows PowerShell.
See [Local Development](docs/development/local-development) for checks and shutdown.

Use **Generate Digest** after analyzing relevant Items, and **View Digest History**
to read persisted briefs. Digests are explicitly AI-generated. The Scheduler is
disabled by default; enable it only in a single backend process without reload.
It scans enabled Topics, analyzes up to 20 pending Items per Topic, and creates a
Digest only when that run successfully analyzes a new relevant Item. See
[local development](docs/development/local-development) for configuration and shutdown.

In a Topic's Item list, **Analyze** updates one Item immediately. **Analyze
Unprocessed Items** processes up to 10 Items sequentially, displays success/failure
counts, and refreshes saved results. Local inference can take several minutes.
Unanalyzed Items show **Not analyzed**; failed requests display errors without
removing existing results. Configure Ollama as described in Local Development.

## Local Development

For offline collection testing, set `USE_MOCK_SOURCE=true` in `backend/.env` and
restart the backend. No YouTube key is required in this mode. MockSource is only
for local development/tests: it generates three deterministic simulated Items per
query, with local placeholder links. Scan twice to see 3 new Items followed by 3
duplicates. Existing Items remain visible. The default `false` keeps YouTube;
switching back requires a YouTube key and network access. See
[local testing instructions](docs/development/local-development).

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

Use **View items** on a Topic to read saved content without scanning. **Scan** calls
the YouTube collection API, displays Fetched / New / Duplicates, and refreshes that
Topic's Items. **Refresh items** reloads saved content. Scans use real YouTube API
quota; loading and failure messages appear within the Topic. Original links open
in a new tab.

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
