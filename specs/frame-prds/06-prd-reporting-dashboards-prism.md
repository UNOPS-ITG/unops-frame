# PRD 06: Reporting, Dashboards, and the Prism Handshake

## Purpose

Teams need answers where they work; the organization needs analytics in one governed place. Frame ships operational reports and dashboards, and replicates organizational-tier data to Postgres for Prism. The boundary is architectural, not aspirational.

## Scope

In: report builder, dashboard composition, sharing, the replication pipeline, the Prism contract. Out: semantic-layer modeling, cross-domain analytics, official KPIs (all Prism).

## Functional requirements

### Reports

**RP-1 (P1).** Row-level reports over one Blueprint: filters (shared grammar), sorts, grouping with aggregates, column selection, saved and shareable like views. Reports are views with a reporting hat; they reuse the view engine and inherit trimming and transparency annotations.

**RP-2 (P2).** Cross-Blueprint reports along declared relationships and parent-child (project with risk rollups; deliverables across agreements), one relationship hop in v1, consistent with the formula scope decision.

**RP-3 (P2).** Scheduled report delivery: email or Chat with a rendered snapshot and a link, respecting each recipient's own trim at send time (per-recipient render, not one snapshot for all; the cost is accepted for correctness).

### Dashboards

**RP-4 (P2).** Dashboard composer: metric tiles (count, sum, avg with comparison period), charts (bar, line, pie, stacked; rendered with our standard charting), embedded views, embedded report tables, text/markdown tiles, and filter controls that scope the whole dashboard. Data refresh live-on-open plus manual refresh; no long-poll dashboards in v1.

**RP-5 (P2).** Dashboard sharing follows view rules: a lens, never a grant; every tile trims per viewer; annotated aggregates per PM-5.

**RP-6 (P3).** Dashboard embedding in Confluence and intranet pages (PRD 09), viewer-authenticated.

### Replication and the Prism handshake

**RP-7 (P2).** On promotion to organizational tier, the engine generates a Postgres schema from the Blueprint: parent table, child collections as related tables with foreign keys, typed columns from field metadata, soft-delete and version columns, and provenance columns. Schema evolution follows Blueprint versioning with generated migrations; breaking Blueprint changes gate on a successful replica migration plan.

**RP-8 (P2).** Change data flow: Firestore writes to organizational rows stream to Postgres via the event pipeline (Pub/Sub consumer, idempotent upserts, ordering per row), lag target under 60 seconds p95, with lag monitoring and backfill tooling. Replication carries full row data under a replication service principal; the Postgres layer re-applies access control for its consumers via Prism's entitlement model (entitlement-aware cache keying as established in Prism), so trimming exists on both sides of the boundary, implemented once per side.

**RP-9 (P2).** The Prism contract: Prism consumes Postgres schemas and a machine-readable Blueprint descriptor (field semantics, sensitivity markers, relationship map) so the semantic layer can model Frame data without manual re-description. Frame publishes the descriptor on every Blueprint version; Prism decides what it models. Neither system calls the other synchronously in a user path.

**RP-10 (P3).** Team-tier data is not replicated. If a team wants Prism-grade analytics, the path is promotion. This is an incentive by design, stated in product copy.

## Dependencies

PRD 01 (schema generation source), PRD 04 (event stream), PRD 05 (per-viewer render), Prism (consumer contract, jointly owned document).

## Open questions

1. Chart rendering library standardization with Prism to avoid two chart stacks; likely adopt Prism's choice.
2. Snapshot retention for scheduled reports (evidence value vs storage and sensitivity); proposal: link-first, snapshot retention 90 days, restricted fields never in snapshots.
3. Whether report aggregate annotations ("N not visible") should appear in scheduled email renders sent to mixed audiences, or whether mixed-audience schedules should be disallowed. Leaning: allowed, annotations included, because that is what the transparency principle means.
