# SignalRadar architecture

## YouTube collection

```text
Topic
↓
Collection Service
↓
YouTubeSource
↓
YouTube Data API
↓
Normalized Item
↓
PostgreSQL
```

`POST /api/topics/{topic_id}/scan` runs synchronously. CollectionService checks the
Topic, uses exactly Topic.name as the query, calls YouTubeSource, and passes each
normalized result to ItemService. No scheduler, keyword expansion, or pagination.
An explicit scan is allowed even for a disabled Topic; enabled is not a scheduling
policy in this version.

YouTubeSource implements SourceAdapter.search. It calls the official search.list
endpoint once with part=snippet, type=video, maxResults=15 and an API key. It has a
15-second HTTP timeout and no automatic retries. All results are validated before
persistence; malformed responses fail the scan. Titles/descriptions/channel names
have HTML entities decoded. No raw vendor JSON is stored.

The collection transaction uses ItemService.insert_if_new with database
ON CONFLICT (source, external_id) DO NOTHING. Only that identity conflict is skipped;
other database failures roll back the scan. A successful scan reports fetched,
created and duplicates, where fetched = created + duplicates. Duplicate occurrences
within one response also count. Global identity uniqueness means a video already
attached to another Topic counts as duplicate and is not reassigned.

`GET /api/topics/{topic_id}/items` returns Items in collected_at DESC, id DESC order.
It has no pagination or filtering. Missing Topics return 404. Missing API keys
return 503, upstream timeouts 504, and upstream HTTP/network/invalid-data errors
502. No upstream response bodies, keys, or tracebacks are returned to clients.

YOUTUBE_API_KEY is loaded from environment or the ignored backend/.env. HTTPX is
used directly, without a Google SDK. Offline tests use HTTPX MockTransport and a
fake key; local PostgreSQL tests use rollback-only test data and no YouTube calls.
A real YouTube smoke test requires a user-configured key and is manual.

No RSS, Web Search, embeddings, semantic deduplication, clustering, crawling,
or remote notifications are implemented.

## Local operation and Windows notifications

Successful scheduler Digest commit → NotificationService → WindowsNotificationService
→ local Windows toast. A notification requires new relevance AND a saved new Digest;
manual generation, unchanged runs and failed jobs do not notify. This conservative
completion rule avoids notifications without a ready brief. The default-off
NOTIFICATIONS_ENABLED switch disables only delivery. Factory/send failures are
caught separately, log Topic ID only, and do not undo business writes or fail jobs.

Windows delivery uses a fixed PowerShell script and built-in WinRT ToastNotificationManager.
Topic text is passed as stdin JSON and inserted using XML text nodes, never shell
interpolation. PowerShell runs hidden with a 10-second timeout. The existing Windows
PowerShell Start-menu identity is reused; no registry, service or shortcut changes.
An interactive Windows session is required. Windows notification preferences/Focus
Assist may suppress a popup; sent means the Windows delivery call returned, not
proof the user saw a banner. No remote notification transport is implemented.

start-signalradar.ps1 validates local prerequisites, builds Next.js and invokes the
Python local runtime. Uvicorn runs once in the foreground without reload; the Next
production child binds loopback and streams logs to standard logging. Ctrl+C lets
FastAPI stop its scheduler before cleaning up the owned frontend process tree.
Logs rotate at 2 MB with three backups. The launcher does not install/start services,
register auto-start, keep Windows awake, or recover after reboot. Keep its terminal
and logged-in Windows session open. Status probes use SELECT 1 and local Ollama tags,
never inference; they use bounded timeouts and return sanitized states only.

## Topic Digest and local Scheduler

```text
Scheduler → Topic → Collection Service → Item → AI Analysis → Relevant Items
→ Digest Service → AI Provider → Digest → PostgreSQL → Frontend
```

DigestService selects up to 20 analyzed relevant Items, ordered by
COALESCE(published_at, collected_at) DESC then id DESC. The AI input contains Topic
name/description and Item title/source/author/published_at/ai_category/
ai_relevance_score/ai_summary. Raw snippets and full text are excluded. A separate
JSON schema requires title and summary; the prompt prioritizes important new
information, combines obvious repetition, prohibits invented facts, and requests
a moderate-length AI-generated personal intelligence brief. Manual generation
always creates history; no eligible Items returns 409 without calling AI.

The scheduler uses Python threading.Thread, Event.wait and a process-wide Lock,
managed by FastAPI lifespan. Default off; tests never start it. First run occurs
after the configured interval; subsequent intervals start after the prior run
finishes, so no missed-run backlog accumulates. One worker performs all Topics
sequentially with fresh sessions/provider contexts. It checks enabled again before
processing, scans, analyzes at most 20 pending Items, and generates a Digest only
if this run analyzed at least one relevant Item. Older pending Items are included;
already analyzed Items are skipped. Zero new relevance means no automatic Digest.

Each Topic failure is isolated; logs contain IDs/counts but no exception bodies or
secrets. Completed analyses stay saved on later failure. If Digest generation fails,
use manual Generate Digest to recover; this minimal scheduler has no persistent
retry queue. Stop signals prevent subsequent work; an in-flight HTTP request is
allowed to finish or hit its timeout before thread join completes. Use exactly one
Uvicorn process without --reload when enabled; the in-process lock is not a
multi-process or manual-request lock. Keep the scheduler disabled during manual
Scan/Analyze testing to avoid competing work.

## Local Item analysis

```text
Item → AIProvider → OllamaProvider → DeepSeek 8B (configured local model)
     → Structured Analysis → PostgreSQL
```

AIProvider accepts Topic name/description and Item title/snippet/author/source.
OllamaProvider sends these as untrusted metadata to local /api/chat, with a Pydantic
JSON schema in format, stream=false and temperature=0. No full text or external
URLs are fetched. OLLAMA_MODEL selects the installed model; no model is hardcoded.
The HTTP client disables proxies and redirects and accepts only loopback HTTP URLs.
There is a 120-second request timeout and no automatic retry.

AnalysisService validates and saves results and a timezone-aware analysis timestamp.
Single-Item analysis may replace an earlier result; failed attempts retain previous
results. Topic batch analysis selects at most 10 unanalyzed Items, processes them
sequentially, and commits each success. Provider failures leave Items eligible for
retry. There is no background execution or concurrency coordination. Analysis is
model-generated judgment based only on metadata, not verified facts. The prompt
requests 1-3 sentences; validation enforces nonempty text up to 1000 characters.
