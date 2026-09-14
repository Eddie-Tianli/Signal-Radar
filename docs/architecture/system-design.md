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

No RSS, Web Search, AI, embeddings, semantic deduplication, clustering, Digest,
scheduling, crawling, notifications, or new frontend page is implemented.
