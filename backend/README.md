# SignalRadar Backend

FastAPI + SQLAlchemy + local PostgreSQL. The Topic API contract is unchanged.

## Local PostgreSQL setup

The current Windows installation is `D:\postgresql`, listening on port `9912`.
Open PowerShell and connect as the administrator (the password is entered interactively):

```powershell
& 'D:\postgresql\bin\psql.exe' -h 127.0.0.1 -p 9912 -U postgres -d postgres
```

Create a project account and database in psql:

```sql
CREATE ROLE signalradar LOGIN;
\password signalradar
CREATE DATABASE signalradar OWNER signalradar;
\q
```

Choose a project password when prompted. If the account or database already exists,
do not recreate or delete it. For an existing database, use an account that owns it
or has the required schema permissions, and adjust `.env` accordingly.

From `backend/`, copy `.env.example` to `.env` only if `.env` does not already exist.
Set `DB_PASSWORD` to the project password in a local editor. Quote the value if it
contains whitespace or `#`. Keep the password out of chat, source code, and Git.
Environment variables take precedence over `.env`.

## Install, migrate, run

```powershell
cd D:\Projects_ltl\Signal-Radar\backend
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m alembic upgrade head
uvicorn app.main:app --reload
```

Alembic creates the `topics` table and tracks its revision. The application does
not silently create tables or fall back to in-memory storage. Each request uses
a separate session; successful writes are committed and the session is closed
after the request. PostgreSQL generates topic IDs.

Swagger: http://127.0.0.1:8000/docs

## Verify persistence

1. Apply the migration, then create a topic through Swagger or the frontend.
2. Record its ID and query it with `GET /api/topics/{id}`.
3. Stop Uvicorn with Ctrl+C and start it again.
4. Query the same ID; its fields should still be present.
5. Verify edit and delete through the existing frontend at http://localhost:3000/topics.

Existing in-memory topics from the previous implementation cannot be recovered
after the old process stopped. This migration starts with an empty table.

## Automated tests

```powershell
python -m pytest -q
```

The default tests run migrations and CRUD against isolated temporary SQLite files,
including reconnecting with a new engine and migration rollback. They never use
the configured development database. SQLite is only a test fixture, not an
application fallback; these tests do not replace live PostgreSQL verification.

For future model changes, generate a migration with `python -m alembic revision
--autogenerate -m "describe change"`, review it, then apply it with `upgrade head`.
Do not downgrade a database containing needed data: the initial migration's
downgrade deletes the topics table.
