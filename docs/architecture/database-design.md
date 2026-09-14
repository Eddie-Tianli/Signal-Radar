# Database design

```text
topics 1 ─── N items
```

PostgreSQL is the runtime database. SQLAlchemy maps tables; Alembic migration
`0001` creates topics and `0002_create_items.py` creates items. Existing applied
migrations are retained unchanged.

## Items

| Field | PostgreSQL type | Rules |
| --- | --- | --- |
| id | integer / serial | Primary key, database generated |
| topic_id | integer | NOT NULL, foreign key to topics.id, indexed |
| source | varchar(100) | NOT NULL, stable source namespace |
| external_id | varchar(500) | NOT NULL, stable ID within source |
| title | text | NOT NULL; schema/service reject blank text |
| url | text | NOT NULL; schema/service reject blank text |
| author | text | Nullable |
| published_at | timestamp with time zone | Nullable; input requires timezone |
| snippet | text | Nullable |
| collected_at | timestamp with time zone | NOT NULL, database CURRENT_TIMESTAMP |

`uq_items_source_external_id` enforces global uniqueness of `(source, external_id)`.
It is not topic-scoped: the same external content cannot be stored for two Topics.
Supporting multi-topic attribution would require a future association model.
Adapters must produce consistent namespaces and IDs (feed-local IDs should include
feed identity). This is identity deduplication, not semantic deduplication.

`fk_items_topic_id_topics` rejects missing Topics and cascades Item deletion when
its Topic is deleted. ORM navigation is `TopicRecord.items` / `ItemRecord.topic`.
`passive_deletes="all"` leaves deletion to PostgreSQL even for loaded relationships.

Pydantic rejects null/empty/whitespace-only title and URL through ItemCreate and
ItemService. Database NOT NULL rejects nulls, but direct raw SQL bypasses the
Pydantic blank-string rules; internal callers should use the service.
