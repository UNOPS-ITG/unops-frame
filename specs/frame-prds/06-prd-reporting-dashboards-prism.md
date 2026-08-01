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

**Frame offers no permission bypass on any tile, at any tier.** This is a deliberate, named difference from the incumbent, whose dashboard report widget explicitly shows data to viewers who are not shared to the source sheets. A viewer here sees annotated withheld counts instead, and a migrating team that relied on the bypass must be granted a scoped read — which is the honest form of what the bypass was doing implicitly. Named in product copy and in IN-14's migration report so it arrives as a documented decision rather than a "the dashboard is broken" ticket.

**RP-11 (P2).** Queued execution. Report runs above a cost or duration threshold execute asynchronously rather than on the request path, which Cloud Run's request timeout makes necessary rather than optional; the requester is notified on completion through NT-1 consuming a `frame.report.run_completed` event. **A stored result is never re-served to a different principal.** PM-5 trimming applies at render under the requesting principal, and a run whose requester's compiled rule set has changed since execution is re-executed rather than replayed.

**RP-6 (P3).** Dashboard embedding in Confluence and intranet pages (PRD 09), viewer-authenticated.

### Replication and the Prism handshake

**RP-7 (P2).** On promotion to organizational tier, the engine generates a Postgres schema from the Blueprint: parent table, child collections as related tables with foreign keys, typed columns from field metadata, soft-delete and version columns, and provenance columns.

Corporate reference fields (PRD 14) replicate as the **key only**, never as a copy of the dimension. The warehouse already holds the dimension and joining there is the natural act; replicating it would create a second staleness surface and a second entitlement question for no analytical gain. Read-time formulas (BP-9, `materialized: false`) are excluded from the replica by definition, since they have no stored column.

**RP-10a (P2).** The vision's refusal to grow an analytics platform (N2) is implemented here by a single line of rationale, and one capable team lead with an executive sponsor will test it. The concrete pathology worth naming when they do: because the incumbent's metric widgets bind to individual cells, every mature estate maintains "metrics sheets" of cross-sheet formulas — each an unversioned, unowned calculation nobody can reconcile, and precisely the archaeology this product exists to end. Relaxing RP-10 would break three things at once: the only reward for accepting governance that a team lead actually values, Prism's guarantee that anything it models has a steward and a stable schema, and the replica's cost model, since team tier is the long tail. The sentence belongs where a team lead sees it, not only in a PRD. Schema evolution follows Blueprint versioning with generated migrations; breaking Blueprint changes gate on a successful replica migration plan.

**RP-8 (P2).** Change data flow: Firestore writes to organizational rows stream to Postgres via the event pipeline (Pub/Sub consumer, idempotent upserts, ordering per row), lag target under 60 seconds p95, with lag monitoring and backfill tooling. Replication carries full row data under a replication service principal; the Postgres layer re-applies access control for its consumers via Prism's entitlement model (entitlement-aware cache keying as established in Prism), so trimming exists on both sides of the boundary, implemented once per side.

**RP-9 (P2).** The Prism contract: Prism consumes Postgres schemas and a machine-readable Blueprint descriptor (field semantics, sensitivity markers, relationship map) so the semantic layer can model Frame data without manual re-description. Frame publishes the descriptor on every Blueprint version; Prism decides what it models. Neither system calls the other synchronously in a user path.

**RP-10 (P3).** Team-tier data is not replicated. If a team wants Prism-grade analytics, the path is promotion. This is an incentive by design, stated in product copy.

## Dependencies

PRD 01 (schema generation source), PRD 04 (event stream), PRD 05 (per-viewer render), Prism (consumer contract, jointly owned document).

## Open questions

1. Chart rendering library standardization with Prism to avoid two chart stacks; likely adopt Prism's choice.
2. Snapshot retention for scheduled reports (evidence value vs storage and sensitivity); proposal: link-first, snapshot retention 90 days, restricted fields never in snapshots.
3. Whether report aggregate annotations ("N not visible") should appear in scheduled email renders sent to mixed audiences, or whether mixed-audience schedules should be disallowed. Leaning: allowed, annotations included, because that is what the transparency principle means.
