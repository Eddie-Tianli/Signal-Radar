# SignalRadar architecture

## Content flow

```text
Topic
↓
Collection Layer
↓
Source Adapter
↓
Normalized Item
↓
PostgreSQL
```

Item is the unified internal content model for all future information sources.
Platform-specific response formats belong inside adapters, not database tables.
This keeps downstream persistence and later presentation independent of vendor APIs.

Implemented foundation:

- `SourceAdapter.search(query) -> list[NormalizedItem]` is a synchronous abstract
  contract, with no network implementation and no database writes.
- `NormalizedItem` contains source identity and content fields, without local IDs.
- Internal callers attach `topic_id` using `ItemCreate`, then call
  `ItemService.create_item`. `id` and `collected_at` come from PostgreSQL.
- `ItemService.list_topic_items` returns ordered Item read schemas.
- Duplicate identities and invalid foreign keys raise SQLAlchemy IntegrityError;
  failed service writes roll back the session. The service commits each successful
  insert, matching TopicService's transaction convention.
- FakeSource lives only in tests and proves normalization-to-persistence without
  internet access. There is no collection runner, registry, scheduler, or live source.

Topic CRUD and its frontend remain unchanged. No Item HTTP API, YouTube/RSS/Web
integration, AI, crawling, clustering, authentication, or deployment is implemented
by this foundation.
