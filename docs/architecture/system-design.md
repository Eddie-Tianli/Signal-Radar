# SignalRadar architecture

## Implemented content foundation

```text
Topic
↓
Source Adapter
↓
Normalized Item
↓
PostgreSQL
```

This is the implemented contract and persistence foundation, not a running
collection pipeline. There is no live Source or collection orchestrator yet.

- Topic CRUD and PostgreSQL persistence are available.
- `SourceAdapter.search(query: str) -> list[NormalizedItem]` defines a minimal
  synchronous adapter interface. Adapters isolate platform-specific data formats
  and must not write to the database. No registry or dynamic loading is used.
- `NormalizedItem` provides the common source identity and content fields.
  A caller supplies the local Topic via `ItemCreate`; `Item` is the read schema,
  following the existing `Topic` naming style.
- `ItemService.create_item` validates input and commits a database record.
  Invalid Topic references and duplicate identities are rejected by database
  constraints; failed writes roll back the session. `list_topic_items` returns
  Items for one Topic in ID order (an unknown Topic yields an empty list).
- PostgreSQL generates IDs and collection times. Topic/Item navigation is
  bidirectional; deleting a Topic cascades to its Items.

FakeSource exists only in tests and demonstrates query → normalization → internal
persistence without internet access. Future YouTube, RSS, and Web Search adapters
must translate their responses into the same model rather than leaking vendor
formats into storage and downstream processing.

No real source integration, network collection, Item API/page, scheduler, crawler,
AI, embeddings, semantic deduplication, clustering, or Digest is implemented here.

See [database design](database-design.md). The PRD and ADR-002 retain the earlier
planning context; this document records the current implemented foundation.
