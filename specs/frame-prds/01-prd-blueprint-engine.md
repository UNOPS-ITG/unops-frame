# PRD 01: Blueprint Engine

## Purpose

The Blueprint engine is Frame's foundation: the metadata service that defines what everything else renders, validates, permissions, and automates. Every other PRD depends on this one. It must make the Frappe DocType idea invisible to Maya, powerful for Daniel, and governable for Ingrid.

## Scope

In: Blueprint schema definition, field types, validation, relationships, parent-child composition, computed fields, versioning, provenance and attribution, the promotion ladder, the catalog, the AI-assisted promotion review, lifecycle policies. Out: rendering (PRD 02), permission evaluation semantics (PRD 05), event publication details (PRD 04).

## Functional requirements

### Blueprint definition

**BP-1 (P1).** A Blueprint is a versioned JSON document in Firestore defining: identity (id, name, description, icon, tier, workspace), fields, relationships, children, permission rules, workflow states and transitions, computed fields, view defaults, lifecycle policies, and provenance. The schema of the Blueprint document itself is versioned independently (metaschema version) so the engine can migrate old Blueprints forward.

**BP-2 (P1).** Field types at launch: text (single, long, rich), number (integer, decimal, currency with ISO code, percent), date, datetime, duration, boolean, single select, multi select, user (resolving Google identity), group (resolving Google Group), attachment (Drive-backed), URL, email, phone, reference (link to a row of another Blueprint), rollup (aggregate over a relationship or child collection), formula (computed), auto-number, created/modified stamps. P2 adds: geolocation, rating, barcode, JSON (escape hatch, admin-gated).

**BP-3 (P1).** Every field supports: required, unique (within Blueprint scope), default value, validation rule (declarative: range, regex, length, allowed values, cross-field conditions), help text, and a sensitivity marker (plain, sensitive, restricted) that PRD 05 consumes.

**BP-4 (P1).** Declarative validation is evaluated server-side on every write regardless of channel (grid, form, API, import, bound Sheet, automation). There is exactly one validation path.

### Parent-child composition

**BP-5 (P1).** A Blueprint may declare named child collections, each referencing a child Blueprint. A child row belongs to exactly one parent row. Deletion, archival, and freeze cascade from parent to children. Save of a parent with modified children is transactional (Firestore subcollection writes within a batch/transaction, parent as the boundary).

**BP-6 (P2).** Children may declare their own children (grandchildren). Depth is capped at 3 levels; the cap is a product decision to keep UI and query complexity sane, revisited only with a concrete use case that survives scrutiny.

**BP-7 (P1).** A parent may declare multiple child collections (a project with milestones, risks, and stakeholders). Each collection has its own child Blueprint, ordering rule, and permission composition per PRD 05.

**BP-8 (P2).** Child rows are also queryable flat across parents ("all deliverables due this month"), served by a collection-group index, with parent context joined into results and parent-permission ceilings enforced.

### Computed fields and formulas

**BP-9 (P1).** Formula fields support row-scope expressions (arithmetic, string, date, logical, conditionals) over the row's own fields, evaluated server-side on write and materialized. The formula language is a single, documented grammar shared with automation conditions and report filters. One language, everywhere.

**BP-10 (P2).** Rollup fields aggregate over a child collection or a reference relationship: count, sum, min, max, avg, latest, concat, and filtered variants. Recalculation is event-driven via the dependency graph (see BP-11) with eventual consistency target under 5 seconds p95.

**BP-11 (P2).** The engine maintains a formula dependency graph in Postgres for promoted Blueprints (and in-memory for team tier), detecting cycles at Blueprint save time and rejecting them with a comprehensible error. Cross-Blueprint formula references are limited to one relationship hop in v1 (vision risk note: conservative scope is deliberate).

### Versioning and provenance

**BP-12 (P1).** Every Blueprint edit creates a new version with author, timestamp, and a structural diff. Rows record which Blueprint version they were last validated against. Non-breaking changes (adding optional fields, relaxing validation) apply immediately; breaking changes (type changes, removing fields, tightening validation) require an explicit migration step that reports which rows would fail and offers remediation (default fill, transform, or quarantine to an exceptions view).

**BP-13 (P1).** Provenance metadata: original author, contributors (anyone whose Blueprint edit was accepted), forked-from lineage, AI-assistance flags per BP element. Provenance is append-only.

**BP-14 (P1).** Attribution surfaces: the catalog entry and the Blueprint's info panel display the credit line ("thanks to the work of X, Y") and adoption stats (workspaces using it, row count governed, forks). Credit is never removable by promotion; stewards may add contributors, never delete the original author.

### Promotion ladder

**BP-15 (P1).** Tiers and their contracts. Personal: private to the creator, minimal ceremony, fields may be untyped text until the user types them. Team: shared within a workspace, fields must be named and typed, appears in workspace search. Organizational: published to the catalog, steward-approved, replicated to Postgres, eligible for event contract consumers, subject to data standards.

**BP-16 (P1).** Promotion from personal to team is self-service with an inline typing wizard (AI-assisted field type inference from existing data, user confirms).

**BP-17 (P2).** Promotion to organizational tier opens a review case for the domain steward containing the AI-prepared working file: catalog similarity scan with field-by-field diff against nearest matches, naming and type normalization suggestions against our data standards, inferred validation rules from actual team-tier data, permission gap flags (fields that look sensitive but are unrestricted, informed by field content classification), and a draft migration plan for look-alike trackers. The steward approves, approves with changes, requests changes, or rejects, all recorded. Promotion is a database-level act: the approved Blueprint publishes to the environment's catalog directly, with no deployment involved (per the index's configuration architecture section, user-authored artifacts at every tier are data, not code-first config). Target: under 30 minutes of steward attention for a routine case; median promotion cycle under 5 working days, measured and reported.

**BP-18 (P2).** Demotion and deprecation: organizational Blueprints can be deprecated (no new instances, existing continue) with a designated successor and a migration assist. Nothing is deleted while rows reference it.

### Catalog

**BP-19 (P2).** The catalog is browsable and searchable by name, domain, field semantics ("has a vendor field", "tracks risks"), and steward. Each entry shows description, credit line, adoption stats, version history, and a one-click "use this" that instantiates it in the requester's workspace with a link back for schema updates (subscribe to upstream versions, with opt-in update application).

**BP-20 (P2).** Duplicate pressure: when a user creates a new team-tier Blueprint, the engine runs the similarity scan and, above a threshold, suggests the catalog entry instead ("This looks like Vendor Register, used by 14 teams"). Suggestion, never a block.

### Lifecycle

**BP-21 (P2).** Lifecycle policies per Blueprint: retention period, archival rules (archived rows leave active indexes but remain auditable), freeze (row becomes immutable, e.g. after approval), and legal hold override. Enforcement is server-side and logged.

## Data model notes

Firestore layout: `workspaces/{ws}/blueprints/{bp}` for metadata, `workspaces/{ws}/rows/{bp}/{row}` with children as subcollections `.../children/{collection}/{childRow}`. Organizational Blueprints additionally registered in a root `catalog` collection. Postgres receives normalized replicas for organizational tier (PRD 06 owns the replication pipeline; this PRD owns the "children as related tables" mapping generated from Blueprint metadata).

## API

Generated per Blueprint from metadata: CRUD for rows and children (child operations addressable both nested and flat), query endpoint honoring the shared filter grammar, metadata read, OpenAPI spec published per Blueprint version. Admin API for Blueprint CRUD, promotion, and catalog. All APIs enforce PRD 05 evaluation.

## Dependencies

PRD 05 (permission rule schema is part of the Blueprint document), PRD 08 (AI inference and similarity scan), PRD 06 (Postgres mapping), PRD 04 (events emitted on Blueprint and row changes).

## Open questions

1. Metaschema governance: who approves changes to the Blueprint schema itself (new field types)? Proposal: ITG platform team with steward consultation, quarterly cadence.
2. Similarity scan implementation: embedding-based field semantics vs structural diff heuristics, or both. Spike alongside PRD 08.
3. Unique constraint scope for organizational Blueprints instantiated in many workspaces: per-instance or global? Likely a per-field setting.
4. Whether team-tier Blueprints should support formulas referencing organizational Blueprints (governance asymmetry). Initial position: read-only references allowed, rollups not.
