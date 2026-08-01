# PRD 13: Search Architecture

## Purpose

Search is how a platform with thousands of Blueprints and millions of rows stays navigable: an omnibox that finds the row, the tracker, the catalog entry, or the comment, trimmed to the searcher, in under half a second. It is also a security surface: an index is a copy of your data, and a careless one is a permission bypass with a query box. This PRD defines the search experience, the index architecture, the trimming model, and the engine selection.

## Scope

In: search UX, index pipeline, document model, permission trimming at query time, engine evaluation and recommendation, semantic search posture. Out: ask-this-view natural language answers (PRD 08; that is question answering over one view, not retrieval across the estate), Prism analytics queries, Drive full-content search (Workspace's own search remains the tool for document contents; see SR-6 for the boundary).

## Search experience

**SR-1 (P1).** Omnibox (keyboard-summoned, ever-present): one query across row titles and indexed fields, Blueprint and view names, catalog entries, workspace names, comments, and attachment filenames, grouped by type with keyboard navigation straight into the result. Recent items and frequently opened surfaces before typing.

**SR-2 (P1).** Scoped search: within a Blueprint (the grid's filter bar backed by the same index for text terms, merged with structured filters), within a workspace, or estate-wide, with type filters (rows, trackers, apps, people's assignments).

**SR-3 (P2).** Query features: prefix and fuzzy matching (typo tolerance), phrase quoting, field-qualified terms (`vendor:acme state:open`) mapping onto the shared filter grammar, and result highlighting. Relevance blends text score with recency, the searcher's interaction history with the workspace, and tier (organizational entries outrank personal look-alikes).

**SR-4 (P3).** Semantic retrieval: embedding-based similarity for catalog discovery ("do we track anything like supplier due diligence") and row-level semantic search on steward-enabled Blueprints, aligned with Corpus infrastructure rather than a parallel embedding estate. Ships after Corpus's service boundary is stable; SR-1 through SR-3 do not wait for it.

## Index architecture

**SR-5 (P1).** The index is populated exclusively from the domain event stream (AU-8): an indexer service consumes row, child, comment, Blueprint, and catalog events, builds typed search documents, and upserts them. No dual-write from the data service; if the event contract does not carry it, it is not searchable, which keeps one integration seam and makes reindexing a replay.

**SR-6 (P1).** Document model per row: row id, Blueprint and workspace, title field, indexed text fields, select values, user references (as names and ids), comment text as child documents (per-comment documents for precise snippets, accepting the larger document count), attachment filenames, timestamps, and a permission envelope (below). The per-field searchable toggle (BP-3 addition) defaults on for long-text fields on organizational Blueprints, with steward override per field. Deliberate exclusions: restricted-marked field values are never indexed (the PM open question resolves to exclusion; the utility loss is accepted and measured), attachment file contents are not indexed (Drive search owns file contents; Frame links out), and personal-tier Blueprints index only for their owner (owner-tagged documents, cheapest possible isolation).

**SR-7 (P1).** Permission trimming, two stages sharing PRD 05 as the only authority. Stage one, index-time envelope: each document carries workspace, Blueprint, tier, and the row attribute values referenced by that Blueprint's row-condition rules (the envelope is regenerated when rules change, driving the PM-4 sixty-second propagation target via rule-change reindex of the Blueprint). Stage two, query-time: the query is filtered to the searcher's candidate set (workspaces and Blueprints they hold any read grant on, computed from compiled rules), then results pass through the standard evaluation library batch-wise before rendering, so row-condition rules are enforced by the same code as everywhere else and the index never returns what evaluation would deny. The index accelerates; the evaluator decides. Existence-masked rows (PM-6) carry a mask flag and are dropped in stage two without count disclosure, consistent with masking semantics.

**SR-8 (P1).** Freshness and repair: index lag target under 10 seconds p95 for row events; a nightly consistency sweep compares index checksums per Blueprint against the store and repairs drift; full reindex is an event replay with progress reporting, exercised quarterly as an operational drill, not discovered during an incident.

## Engine selection

A constraint shapes this choice before features do: a dedicated search engine (Typesense, Meilisearch, OpenSearch) is a stateful server holding its index on local disk and staying resident, which cannot run on Cloud Run's ephemeral, scale-to-zero containers. Adopting one means adding a new runtime (a VM group or GKE) to the estate, a real operational cost that should only be paid when search quality demonstrably demands it. The recommendation therefore stays inside our stack:

**Recommendation: a search projection in Postgres.** A dedicated schema in our existing Cloud SQL Postgres holding one narrow row per searchable document: identifiers, title, a tsvector column over the indexed text, trigram indexes (pg_trgm) for prefix and typo-tolerant matching, the permission envelope as columns, and timestamps. Populated by the indexer from the event stream like any consumer. Three things this is not: it is not the analytics replica (RP-10 stands; team and personal tiers appear here as searchable text only, with no analytical value and no relational modeling), it is not a second source of truth (disposable, rebuildable by replay), and it is not new infrastructure (zero new runtimes, standard Cloud SQL operations, CMEK as configured). At our realistic scale, low millions of documents, Postgres FTS with trigram support meets the latency budget with headroom, and ranking (ts_rank blended with recency and tier weighting in the query service) covers SR-3.

**Named upgrade path: Typesense, self-hosted.** If measured search quality or latency outgrows the projection (the honest thresholds: sustained p95 misses, or relevance complaints that tuning cannot fix), Typesense is the successor: open source, vendorable, purpose-built for instant faceted search, taking our permission envelope as filterable attributes. Adopting it is a deliberate infrastructure decision made at that time, with the runtime question (it needs persistent VMs or GKE, not Cloud Run) owned explicitly by ITG operations, not slipped in as a footnote. The indexer and document model are engine-agnostic by design so the swap replaces the storage and query adapters only.

**Rejected.** Managed search services (including Vertex AI Search): we manage embeddings and retrieval ourselves as a matter of posture; semantic capability comes from our own embedding infrastructure via Corpus alignment (SR-4), not a managed black box. OpenSearch/Elasticsearch: more engine than SR-1 through SR-3 need, heaviest operations of the field.

A one-week spike validates the projection: tsvector plus pg_trgm performance with permission-envelope filters at 5 million documents, indexer throughput at replay speed, and p95 query latency under concurrent load, on a Cloud SQL tier we would actually run. Decision owner: Frame lead engineer with ITG operations sign-off.

## Non-functional

Query p95 under 200ms engine-side, under 500ms end-to-end including stage-two evaluation; projection storage budgeted and monitored per workspace; the projection holds no data older than the store (disposable and rebuildable; backups are for recovery speed, durability remains the store's job); access restricted to the indexer and query services.

## Dependencies

PRD 04 (event stream), PRD 05 (evaluation library, envelope definitions, masking semantics), PRD 01 (field metadata drives indexed-field selection; a per-field "searchable" toggle is added to BP-3), Corpus (SR-4 alignment), ITG operations (the new stateful service).

## Decisions log

Resolved August 2026: comments index as child documents (folded into SR-6); the searchable toggle defaults on for long-text fields on organizational Blueprints with steward override (folded into SR-6); people-centric queries ("what is assigned to Maya") are served by a dedicated assignments surface in P2 rather than a search type, since they are a filter over structured fields, not text retrieval. No open questions remain in this PRD.
