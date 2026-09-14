# Database design

## Scope

This is the requested Topic-only implementation baseline plus a Planned Item draft.
It is not a live migration inventory. No database or migration changes accompany
this document; existing repository implementation is not rolled back.

## Topic — Implemented baseline

PostgreSQL stores Topics through SQLAlchemy. Alembic manages schema changes.

| Field | Type | Rules |
| --- | --- | --- |
| id | integer | Generated primary key |
| name | text | Required; application rejects empty or whitespace-only names |
| description | text | Nullable |
| enabled | boolean | Required, default true |

## Item — Planned

```text
Topic 1 ─── N Item
```

One Topic is planned to have many Items; each Item belongs to one Topic.

| Field | Proposed PostgreSQL type | Planned rules |
| --- | --- | --- |
| id | integer | Generated primary key |
| topic_id | integer | Required foreign key to topics.id; index for Topic queries |
| source | varchar(100) | Required, stable source namespace |
| external_id | varchar(500) | Required identifier within source |
| title | text | Required, non-empty |
| url | text | Required, non-empty |
| author | text | Nullable |
| published_at | timestamp with time zone | Nullable |
| snippet | text | Nullable |
| collected_at | timestamp with time zone | System-generated collection time |

A unique constraint on `(source, external_id)` is planned to prevent repeated
storage of the same external content. Adapters should generate consistent source
names and stable IDs; feed-local IDs may need feed identity included.

This proposed uniqueness is global, not Topic-scoped. Combined with the one-Topic
foreign key, a single external content record can belong to only one Topic.
Multi-topic attribution would require a separate association design later.
Deletion policy and detailed migration implementation should be confirmed during
implementation. No Item table creation is performed or claimed by this document.
