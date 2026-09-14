# SignalRadar architecture

## Planning baseline

Topic CRUD with PostgreSQL persistence is the completed baseline for this design.
The flow below is Planned. It is not a live code or migration inventory and does
not imply that this documentation change removes existing code.

## Content Collection — Planned

```text
Topic
↓
Collection Service
↓
Source Adapter
↓
Normalized Item
↓
PostgreSQL
```

- **Topic** provides the user's area of interest and collection context.
- **Collection Service** is planned to coordinate a collection request, invoke an
  adapter, attach the Topic association, validate results, and request persistence.
- **Source Adapter** isolates platform-specific data formats. Future YouTube, RSS,
  and Web Search adapters should all return the same normalized content shape.
- **Item** is the planned unified internal content model, retaining source identity
  without exposing vendor-specific response structures to downstream code.
- **PostgreSQL** is planned to persist Items and enforce their Topic association
  and source/external-ID uniqueness.

Adapters should handle format conversion; persistence should remain separate.
No live source, collection runner, scheduler, or AI completion is claimed here.
See [database design](database-design.md), [PRD](../product/PRD.md), and
[ADR-002](../decisions/ADR-002-unified-content-model.md).
