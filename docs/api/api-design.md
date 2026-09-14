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
No pagination, filters, sorting controls, or Item mutation endpoints are provided.

Swagger is available at http://127.0.0.1:8000/docs.
