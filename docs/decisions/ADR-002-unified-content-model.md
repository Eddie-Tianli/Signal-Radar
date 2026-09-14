# ADR-002: Unified Content Model

Status: Proposed (Content Collection design)

## Context

SignalRadar plans to collect content for user-defined Topics from multiple sources,
including possible YouTube, RSS, and Web Search integrations. Those platforms use
different response formats, identifiers, and metadata. This decision documents the
planned model, not integration completion or the current repository migration state.

## Decision

Use one unified Item model containing Topic association, source identity, title,
URL, optional author/publication time/snippet, and system-recorded collection time.
Source Adapters should normalize platform responses before persistence. Plan a
unique `(source, external_id)` constraint for identity-based deduplication.

Do not introduce YouTubeItem, RSSItem, or WebItem tables in this stage. Do not
predefine AI, embedding, event, or generated-summary fields.

## Alternatives Considered

- **A table per platform:** preserves platform-specific fields naturally but
  duplicates common columns, migrations, queries, and downstream handling.
- **Store only raw platform JSON:** easy to ingest initially but exposes consumers
  to vendor formats and weakens consistent validation and querying.
- **Unified Item:** gives all sources a stable internal contract with nullable
  fields for missing metadata. Chosen for the next-stage design.

## Consequences

- Collection, persistence, and future presentation can share a common contract.
- Adapters must map formats and establish stable source identifiers.
- Some platform metadata will not fit the initial model; add fields only when
  concrete requirements justify them, rather than storing everything now.
- Global source/external-ID uniqueness prevents duplicate identities but does not
  provide semantic deduplication or multi-topic attribution.
- This decision does not implement a source, network request, database migration,
  scheduler, or AI feature.
