# API Design

## v0.1.0 Dashboard

GET /api/dashboard is read-only and returns total_topics, enabled_topics,
total_items, relevant_items (analyzed and true), unanalyzed_items, recent_items
and recent_digests. Recent lists contain at most five rows in timestamp/ID descending
order, with Topic names for display. The first recent Digest is the latest. No
activity table, cached counters or new migration is introduced. Database failure
returns sanitized 503. Runtime status is read separately from GET /api/status.

## Topic management

Existing GET/POST /api/topics and GET/PUT/DELETE /api/topics/{topic_id} retain their
contracts. Topic fields are id, name, description, enabled.

## POST /api/topics/{topic_id}/scan

No request body. Performs one synchronous YouTube search using Topic.name, with
up to 15 video results and no pagination. Returns HTTP 200 after a successful scan:

```json
{"topic_id": 1, "source": "youtube", "fetched": 15, "created": 12, "duplicates": 3}
```

Counts reflect returned normalized results, not YouTube's total search matches.
Repeated scans still request YouTube and consume quota. Existing videos are skipped
by global source/external-ID identity, including videos attached to another Topic.
No content updates or cross-topic reassignment occur. An empty result returns zeros.

Errors use FastAPI's {"detail": "message"} format:

| Status | Meaning |
| --- | --- |
| 404 | Topic does not exist; no YouTube request |
| 503 | YOUTUBE_API_KEY missing, or database write unavailable |
| 504 | YouTube HTTP timeout |
| 502 | Upstream HTTP error, connection failure, or invalid response |
| 422 | Invalid path parameter |

No automatic retries. Database writes are one transaction; malformed upstream
results are rejected before any writes. Current enabled flag does not block manual scans.

## GET /api/topics/{topic_id}/items

Returns HTTP 200 with an array (empty when no Items), ordered by collected_at DESC
then id DESC. Missing Topic: 404. Database failure: 503.

Each Item contains id, topic_id, source, external_id, title, url, author,
published_at, snippet, collected_at. Author, published_at and snippet can be null.
Items also include nullable ai_relevant, ai_relevance_score, ai_category, ai_summary,
and ai_analyzed_at. No pagination, filters, or sorting controls are provided.

Swagger is available at http://127.0.0.1:8000/docs.

## POST /api/topics/{topic_id}/digest

No body. Uses up to 20 analyzed relevant Items and returns a saved Digest:
```json
{"id":1,"topic_id":1,"title":"Topic Brief","summary":"AI-generated content...","item_count":3,"generated_at":"2026-09-15T12:00:00Z"}
```
404: missing Topic. 409: no eligible Items (no AI call). Provider errors use the
same 502/503/504 semantics as analysis, and database failures return sanitized 503.
Each successful manual request creates a new snapshot; there is no automatic retry.

## GET /api/topics/{topic_id}/digests

Returns an array of complete Digests ordered by generated_at DESC, id DESC.
Existing Topic without history returns []; missing Topic returns 404. No pagination
or standalone detail endpoint is implemented. All summaries are AI-generated.

## POST /api/items/{item_id}/analyze

No body. Analyzes one saved Item against its Topic and returns HTTP 200 with the
complete Item including ai_* fields. Repeating explicitly replaces the analysis
only after a successful validated response. Missing Item: 404. Missing model
configuration, missing Ollama model/endpoint, unreachable local service or database
failure: 503. Timeout: 504. Invalid structured output or upstream failure: 502.
Errors use {"detail":"..."}; raw model responses and tracebacks are not exposed.

Structured provider result:
```json
{"relevant":true,"relevance_score":0.87,"category":"news","summary":"A short summary."}
```
Boolean is strict, score must be finite and in [0,1], category has 1-50 characters,
summary has 1-1000 characters. The prompt requests 1-3 sentences. Extra keys are
rejected. The provider schema maps to the corresponding persisted ai_* fields.

## POST /api/topics/{topic_id}/analyze?limit=10

No body. limit is 1-10 (default 10); invalid limits return 422. Only Items with
ai_analyzed_at=null are selected in ID order. Missing Topic returns 404.
```json
{"topic_id":1,"processed":3,"relevant":2,"irrelevant":1,"failed":0}
```
processed counts successful analyses and equals relevant+irrelevant. failed counts
provider failures; attempted count is processed+failed. A batch with provider
failures returns HTTP 200 and nonzero failed; retry a single Item for its detailed
error. Successful Items remain saved if a later request fails. Database failure
returns 503 and earlier committed successes remain. Batches are synchronous and
can take several minutes; no automatic retry, queue, or scheduling is provided.
