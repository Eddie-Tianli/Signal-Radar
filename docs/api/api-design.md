# API Design

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
