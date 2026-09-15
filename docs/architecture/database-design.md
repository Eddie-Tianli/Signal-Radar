# Database design

## Implemented storage

PostgreSQL stores Topics and Items through SQLAlchemy. Alembic revision `0001`
creates Topics; `0002_create_items.py` creates Items. `0003_item_ai_analysis.py`
adds nullable AI analysis fields. `0004_create_digests.py` adds Digest history.
Current head is `0004`.
Previously applied migration files are preserved unchanged.

## Topics

| Field | PostgreSQL type | Rules |
| --- | --- | --- |
| id | integer / serial | Generated primary key |
| name | text | Required; application rejects blank names |
| description | text | Nullable |
| enabled | boolean | Required, default true |

## Items

```text
Topic 1 ─── N Item
```

A Topic owns multiple Items; every Item references one existing Topic.

| Field | PostgreSQL type | Rules |
| --- | --- | --- |
| id | integer / serial | Generated primary key |
| topic_id | integer | NOT NULL, foreign key, indexed |
| source | varchar(100) | NOT NULL, stable namespace |
| external_id | varchar(500) | NOT NULL, stable source identifier |
| title | text | NOT NULL; schema/service reject empty or whitespace-only values |
| url | text | NOT NULL; schema/service reject empty or whitespace-only values |
| author | text | Nullable |
| published_at | timestamp with time zone | Nullable; input requires timezone |
| snippet | text | Nullable |
| collected_at | timestamp with time zone | NOT NULL; database-generated current time |
| ai_relevant | boolean | Nullable until analyzed |
| ai_relevance_score | double precision | Nullable; CHECK between 0 and 1 |
| ai_category | varchar(50) | Nullable; short category |
| ai_summary | text | Nullable; short AI summary |
| ai_analyzed_at | timestamp with time zone | Nullable; successful analysis time |

`fk_items_topic_id_topics` rejects missing Topic references and uses ON DELETE
CASCADE. `TopicRecord.items` and `ItemRecord.topic` use back_populates; passive
ORM deletion leaves cascading to the database. `ix_items_topic_id` supports
queries for one Topic.

`uq_items_source_external_id` enforces global `(source, external_id)` uniqueness,
including writes from different sessions. ItemService rolls back rejected writes
and propagates IntegrityError. Duplicate content is rejected, not silently updated.

Identity is global rather than Topic-scoped: the same external content cannot be
saved under a second Topic. Multi-topic attribution would need a future association
model. Source names and external IDs must be stable; feed-local identifiers may
need feed identity included. This is not semantic deduplication.

Blank-string rules are applied by Pydantic and ItemService. Raw SQL bypasses these
application rules, although database NOT NULL, foreign key, and unique constraints
still apply. `ck_items_ai_score` enforces the score range. Existing rows keep null
AI fields until analyzed. No source-specific columns are included. Downgrading
0003 removes analysis fields/results, while retaining the original Items.

## Digests

Topic 1:N Digest; each Digest references an existing Topic. Deleting a Topic
cascades to its Digests, consistently with Items.

| Field | PostgreSQL type | Rules |
| --- | --- | --- |
| id | integer / serial | Primary key |
| topic_id | integer | Required FK, indexed |
| title | varchar(200) | Required |
| summary | text | Required, AI-generated |
| item_count | integer | Number selected for this brief (1-20 through service) |
| generated_at | timestamp with time zone | Required, database current time |

History is sorted by generated_at DESC, id DESC. Briefs are saved text snapshots;
no Item association table, embeddings or event IDs are added. Migration 0004
preserves existing Topic/Item data; downgrading it removes Digest history.

## Migration commands

From backend with its virtual environment active:

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic check
python -m pytest -q
```

Offline tests use isolated SQLite files with foreign keys enabled for Item tests,
including upgrade from `0001` to `0002`, downgrade, and preservation of Topics.
An opt-in PostgreSQL test validates real constraints and timezone behavior without
internet access. Downgrading `0002` deletes Items; do not run it on needed data.
