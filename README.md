# SignalRadar v0.1.0

SignalRadar is a single-user, Windows-local information intelligence tool. Follow
Topics, collect public metadata, judge relevance with local AI, and read concise
AI-generated briefs. MockSource makes collection available without external APIs.

## Current features

- Dashboard: Topic/Item counts, relevance and pending counts, latest Digest, recent
  Items/Digests and local database/Ollama/Scheduler/notification status.
- Topic CRUD with enabled state; manual Scan and Item lists.
- YouTube Data API source and deterministic development-only MockSource.
- Local Ollama structured Item analysis, single-Item and bounded batch actions.
- Persisted AI relevance, score, category, short summary and analysis time.
- Topic Digests from up to 20 analyzed relevant Items; collapsible history.
- Optional sequential Scheduler: Scan → Analyze pending Items → Digest on new relevance.
- Optional Windows toast after successful automatic Digest creation with new relevance.
- One-command local launcher, dependency checks, graceful shutdown and rotating logs.

## Technology and architecture

Next.js + React + TypeScript + Tailwind CSS; Python + FastAPI; PostgreSQL + SQLAlchemy
+ Alembic; local Ollama; Python standard-library Scheduler and Windows WinRT toasts.

```text
Topics → SourceAdapter → Items → AIProvider/Ollama → Relevant Items → Digest
                         ↓                              ↓
                      PostgreSQL ←─────────────────────┘
                         ↓
                  Dashboard / Topics UI
Scheduler orchestrates the same services; notifications follow successful Digests.
```

Monorepo: frontend/, backend/, docs/. Database head is **0004**; this release adds
no migration. API and frontend product version are **0.1.0**.

## Local setup and running

Prerequisites: Python (tested with the existing project virtual environment),
Node.js/npm, local PostgreSQL and Ollama with an installed model. Startup order is
PostgreSQL → Ollama → SignalRadar. Ollama may be offline when browsing; AI requires it.

One-time setup from repository root in PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
# Only if .env does not exist: copy .env.example .env
# Edit .env with local database credentials and the exact Ollama model name.
python -m alembic upgrade head
cd ..\frontend
npm install
cd ..
.\start-signalradar.ps1 -CheckOnly
.\start-signalradar.ps1
```

For account/database creation see [backend setup](backend/README.md). Never overwrite
an existing .env or commit credentials. The launcher builds Next.js and uses production
mode. Use -SkipBuild only when the existing build matches current source. Keep the
terminal open; Ctrl+C stops the backend gracefully and its frontend process tree.
Open http://localhost:3000; Swagger is http://127.0.0.1:8000/docs. Logs rotate in logs/.

## Environment variables

Configure backend/.env; process environment variables take precedence.

| Variable | Default / purpose |
| --- | --- |
| DB_HOST | 127.0.0.1 |
| DB_PORT | 9912 in this project's local template |
| DB_NAME / DB_USER / DB_PASSWORD | Local PostgreSQL account; password required |
| USE_MOCK_SOURCE | false; true uses deterministic local fixtures |
| YOUTUBE_API_KEY | Required only for real YouTube collection |
| OLLAMA_BASE_URL | http://localhost:11434; loopback HTTP only |
| OLLAMA_MODEL | Exact installed name from ollama list; no business-code default |
| SCHEDULER_ENABLED | false |
| SCAN_INTERVAL_MINUTES | 60; 0.1–10080 supported |
| NOTIFICATIONS_ENABLED | false |

Restart after configuration changes. No service installation, auto-start registration,
model download or Windows configuration change is performed by the launcher.

## MockSource and Ollama

Set USE_MOCK_SOURCE=true for local acceptance. Each query returns three simulated
Items with stable IDs and local placeholder URLs. Repeat scans count duplicates.
Mock content is not factual news and does not require YouTube connectivity.

Start Ollama and run `ollama list`. On the acceptance machine the installed model
is `deepseek-r1:8b`; use your own exact installed tag for OLLAMA_MODEL. MockSource
mocks collection only: Analyze and Generate Digest still use the real local model.
AI text is clearly labeled and may be inaccurate; no full-text retrieval is performed.

## Daily usage

1. Review Dashboard statistics and runtime status.
2. Create a Topic under Topics, then Scan and View items.
3. Analyze individual Items or Analyze Unprocessed Items (up to 10 per request).
4. Generate Digest when at least one Item is relevant; read latest/history.
5. Refresh Dashboard to update its snapshot. Topic links lead to the relevant card.

For automation set SCHEDULER_ENABLED=true and use one backend process, without reload
or multiple workers. The first cycle waits the interval; each next interval begins
after completion. At most 20 pending Items per Topic are analyzed per cycle. No new
relevance means no automatic Digest. Avoid manual operations competing with scheduler.

Set NOTIFICATIONS_ENABLED=true for desktop notifications after a successful automatic
Digest. Windows groups the toast under Windows PowerShell; Focus Assist or notification
settings may suppress it. Manual Digests do not notify. To disable automation safely,
Ctrl+C, set SCHEDULER_ENABLED=false, then restart.

## Validation

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
$env:RUN_POSTGRES_TESTS='1'
python -m pytest -q -p no:cacheprovider --basetemp "$env:TEMP\sr-tests-$([guid]::NewGuid().ToString('N'))"
Remove-Item Env:\RUN_POSTGRES_TESTS
python -m alembic current
python -m alembic check
cd ..\frontend
npm run lint
npm run build
```

Automated tests never call real model/source APIs or show notifications. See
[v0.1.0 acceptance](docs/development/v0.1.0-acceptance.md) for actual local results
and [Local Development](docs/development/local-development) for detailed operations.

## Current limitations

- Single-user local application, no authentication, multi-user support, cloud deployment or mobile app.
- Real YouTube searches need your API key and quota; no other live sources.
- AI depends on local Ollama and available resources; inference may time out.
- Windows notifications require an interactive session and permitted notification settings.
- No background service installation, boot auto-start or recovery after Windows restart/sleep.
- Scheduler locks are process-local; no durable retry queue. If Digest fails after
  analysis succeeds, manually generate it. Disabled Topics are skipped by automation.
- Global (source, external_id) identity means an Item belongs to one Topic only.
- Item/history reads are unpaginated; Dashboard recent lists are limited to five.
- No event clustering, embeddings, vector database or RAG.

## Roadmap (not implemented)

- Improve reliability and usability based on local usage feedback.
- Evaluate pagination and richer source coverage when needed.
- Consider advanced content organization after the local workflow proves useful.

No v0.2.0 work is included in this release.
