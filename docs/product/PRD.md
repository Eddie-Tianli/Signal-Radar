# SignalRadar Product Requirements

## Stage baseline

This document describes the requested planning baseline: Topic management with
PostgreSQL persistence is complete; Content Collection is the next product stage.
Planned statements are design scope, not a live inventory of repository code or
migration state. This documentation task does not revert existing implementations.

## Information Collection / Content Collection — Planned

### Goal

Allow a user-defined Topic to trigger information collection, normalize discovered
external content into Item, and support multiple Sources behind a common boundary.

### Intended flow

1. A Topic supplies the collection context and query.
2. A Collection Service invokes a selected Source Adapter.
3. The adapter maps external content to the unified Item fields.
4. Validated Items are associated with the Topic and saved to PostgreSQL.
5. Repeated source/external-ID pairs do not create duplicate records.

Initial triggering should be explicit; scheduling and background task infrastructure
are outside this design. Detailed API and user-interface behavior will be defined
when implementing collection.

### Planned acceptance criteria

- Every collected Item references an existing Topic.
- All sources produce the same internal content structure.
- Title and URL are required; author, snippet, and publication time may be absent.
- Collection time is recorded by the system.
- Source identity is retained so duplicate external content can be recognized.
- A future additional source can reuse the same persistence model.

YouTube, RSS, and Web Search are candidate sources only, not completed integrations.
AI has not started in this product baseline. Crawling, full-text retrieval,
embeddings, semantic deduplication, clustering, digests, and login are out of scope.
