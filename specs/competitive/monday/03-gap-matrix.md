# Monday.com Enterprise vs Frame — gap matrix

> Analysis date: 2026-08-02 · Analyst: Claude session for tushard@unops.org
> Sources fetched this session: see 01-profile.md header (same set).
> Frame evidence: greps and file reads in this repo this session.
> Shelf life: pricing/changelog claims stale after ~1 quarter.

Status legend: superior · partial · absent · planned (PRD-only) ·
blocked by design (see SKILL.md for definitions)

| Their feature | Frame module / PRD | Status | Evidence |
|---|---|---|---|
| Board grid (items, groups, column types, editing) | `src/grid/FrameGrid.tsx`, `src/grid/cells.ts`, `src/registers/RegisterPage.tsx` | partial | Grid is built and real; Gantt/board/calendar morphing is PRD 02 (GR-*) only — no view-morph code in `src/grid/` |
| Saved views, filters | `functions/lib/views/` (model/store/validate), `src/grid/FilterBuilder.tsx`, `functions/api/routers/views.py` | partial | Views router + validation exist; sharing/permission-trimmed saved views per GR-11 not yet complete |
| Board scale (10K std / 100K Enterprise; mondayDB 3.0 → 1M) | Vision §10 performance budget: 10K rows @60fps, 50K windowed | partial | Budget specified, grid built; no load harness evidence this session. Monday's Enterprise cap (100K) exceeds Frame's stated budget — but Frame keeps all capabilities at scale, unlike the incumbent pattern of shedding features |
| Automation recipes (trigger+condition+action, gallery, metered actions) | `specs/frame-prds/04-prd-automation-and-workflow.md` (AU-1, AU-3, AU-3a) | planned (PRD-only) | Zero automation hits in `src/` and `functions/` (grep: only incidental matches in `src/corporate/`); no automations router in `functions/api/routers/`. Frame's conditions grammar already exists and is shared: `functions/lib/grammar/` (ast/evaluate/compile_query) |
| Cross-board AI workflow builder (branches, waits, AI blocks, MCP block) | AU-8..AU-13 event contract + Workflow Studio; CLAUDE.md/N3: no BPMN designer in Frame | planned (PRD-only) + partially blocked by design | Frame deliberately externalizes flowchart-grade workflow to Workflow Studio over a Pub/Sub event contract; the *user outcome* (multi-step cross-Blueprint process) is achievable via graduation (vision appendix), never via an embedded builder |
| Board roles (5 roles, per-category granularity, Enterprise) | `functions/lib/permissions/evaluate.py`, `model.py`, `trim.py`; PRD 05 PM-1..PM-4 | superior | One pure evaluator, compiled ABAC rules, deny-beats-allow, field-set + row-condition allows, parent ceiling (`evaluate.py:1-21`). Monday's model is named role slots per board; Frame's is arbitrary attribute rules evaluated in one place — and no per-board re-configuration |
| Item-level permissions (visibility via designated People columns only) | PM-2 row conditions over any field; `functions/lib/grammar/evaluate.py` | superior | Monday can express "assigned person sees item" [verified-snippet]; Frame's row conditions take any field, operator, and subject attribute (`CompiledRule.condition: Expr`), plus typed restricted stubs and transparency annotations (PM-5) which Monday has no equivalent of |
| Column view/edit restrictions (Pro+) | Field-set allows + sensitivity bands in `functions/lib/permissions/model.py`, trimming in `trim.py` | superior | Same evaluator handles field trim on every channel incl. audit deltas (`functions/lib/rows/audit.py:8-12`); Monday's column restrictions are per-board settings |
| Audit Log API (security/admin events, SIEM export, Enterprise-only) | `functions/lib/rows/audit.py` (PM-7 typed classes: CHANGE / ACCESS / GOVERNANCE) | superior (design), partial (build) | Monday's catalogue covers logins/exports/permission changes, not data deltas [verified — developer.monday.com]. Frame's CHANGE class carries field-level before/after trimmed by the same permission Decision; ACCESS class audits restricted reads. No query API surface yet |
| Admin estate visibility (verified gap: admins can't see/administer unowned boards; board duplication sprawl) | BP-15..BP-19 promotion ladder + catalog; PM-13 exposure register; PM-7 GOVERNANCE audit class | planned (PRD-only) | Monday's own community forum documents the blind spot [verified]; Frame's catalog/tier model is designed to answer exactly this, but no catalog surface exists in code yet (`functions/lib/blueprint/store.py` has no tier/catalog queries) |
| Managed templates (master → ≤1,000 instances, publish-propagate; 20 free then paid) | Blueprint promotion ladder BP-15..BP-19; org-tier Blueprints | planned (PRD-only), superior design | Monday standardizes by *copy propagation* (template instances are still separate boards); Frame standardizes by *reference* (one org Blueprint, many views) — no instance drift to reconcile, no instance quota to sell. Nothing built yet |
| Managed columns (centrally locked column defs) | Field type registry `functions/config/field_types.json` + org-tier Blueprint fields (BP-3) | partial | Registry exists as code-first config; org-tier locking is PRD-only |
| Data Validation Rules (May 2026) | `functions/lib/blueprint/validate.py`, `functions/lib/rows/writer.py` validation against compiled metadata | partial→superior | Frame validates rows against Blueprint metadata in the one writer (BP-4); Monday added lifecycle validation rules only in May 2026. Frame's grammar-based conditional validation (BP-3a) is specified but the basics are built |
| SCIM provisioning + multi-vendor SSO | Google Identity + IAP only, v1 (00-prd-index NFR: Security) | blocked by design (deliberate non-goal) | Frame is single-tenant, single-IdP by design; SCIM solves a multi-IdP SaaS problem Frame does not have. Honest note: this is a real gap only if Frame ever serves sister agencies (N12 keeps the path open) |
| BYOK / tenant-level encryption | CMEK on Firestore/Postgres (index NFR: Data residency) | partial | Equivalent outcome by construction (our GCP, our keys); not a differentiator either way — vision §10 explicitly drops residency/keys as arguments |
| Audit-to-SIEM (Splunk add-on) | PM-7 audit stream; no export surface | planned (PRD-only) | No SIEM/export code; estate logging conventions would apply |
| Portfolio management (portfolio↔project drill-down, intake provisioning) | PRD 06 (RP-*) dashboards + cross-Blueprint rollups; N2 bounds analytics to Prism | planned (PRD-only) | No dashboard code in `src/`. Frame's answer is rollups over governed relationships + the Prism handshake (RP-10), not a separate portfolio product |
| Resource management (Capacity Manager, Resource Directory) | Vision N11: explicitly not building | blocked by design | N11 names it a distinct product category; no PRD covers it, deliberately |
| Workdocs | Vision N1: no document editor | blocked by design | Workspace (Google Docs) exists; Frame generates documents (PRD 07 DG-*), it does not host authoring |
| Forms (WorkForms, portal intake) | PRD 03 (FM-*); `src/registers/NewRow.tsx` is internal row creation only | planned (PRD-only) | No form builder, no public form surface in code; FM-5/FM-8 specify the external edge |
| Apps marketplace (850+ apps, 3rd-party framework, revenue share) | PRD 10 App Composer | planned (PRD-only), different intent | Frame composes *internal* role-scoped apps from governed Blueprints; no third-party app framework, no marketplace ambition in v1 (N12). See 04-opportunities O5 for why this is a simplification, not a gap |
| Sidekick / agent builder / AI blocks / credits | PRD 08 AI layer (native assists) + N4 (Playbook boundary); MCP surface (Phase 3) | planned (PRD-only) | No AI code in repo. Frame's differentiated piece is specified: MCP tools returning permission-trimmed, transparency-annotated data (vision Pillar 6) — Monday's agents have activity logs but nothing equivalent to trimmed-set annotations |
| AI Admin Usage dashboard (spend per user/team) | PRD 08 + estate AI-gateway conventions | absent | No PRD requirement found for per-team AI cost attribution inside Frame (gateway-level governance exists estate-wide); genuine gap worth an AU/AI PRD amendment |
| GraphQL API, metered per tier (1K–25K calls/day) | Generated REST from compiled metadata: `functions/api/routers/` (generic only) + `src/api/client.ts` typed envelope | superior (design), partial (build) | Frame's API is generated, typed at the envelope, and unmetered (internal platform, no seat/usage monetization); routers exist and are generic per CLAUDE.md break #1 |
| Connect boards / mirror columns (cross-board relations) | Cross-Blueprint references (BP-10, GR-22 reference-path formulas); corporate bindings `functions/lib/corporate/` | partial (in-app refs planned) / superior (corporate data) | Monday's relations are in-app links with documented permission oddities [verified-snippet — connect/mirror permissions article]. Frame's corporate module is *built* (resolve, probe, sweep, executor, classify — 13 modules) and does what no SaaS can: resolve against the org warehouse under the reader's own credentials |
| Guest access / external editors (seat-model sharing) | N7/index Participation: forms + magic links only, no external editing | blocked by design | Monday's guest model defends a seat count; Frame has no seats to defend and deliberately narrows the external surface (PM-13 exposure register) |
| Notification system (mentions, digests) | PRD 12 | planned (PRD-only) | No notification code |
| Content directory / search | PRD 13 (SR-*) | planned (PRD-only) | No search code |

## Reading the matrix

**Where Frame is genuinely behind.** The entire *packaging* layer: automation
recipes a non-technical user assembles in minutes, forms, dashboards,
portfolio rollups, notifications, and any AI surface. All of it is specified
(PRDs 03, 04, 06, 08, 12) and none of it is built. Monday's decade of recipe
templates and its 850-app ecosystem are real accumulated assets. Also
genuinely behind, and *not* yet specified: per-team AI cost attribution
inside the product (their AI Admin Usage dashboard), and proven scale beyond
Frame's 10K/50K budgets against their 100K→1M item roadmap.

**Where "behind" is actually "not yet built but designed better."** The
governance core. Monday's Enterprise tier is a permission/audit/
standardization overlay bolted onto boards that have no semantics: item
permissions can only key off People columns, audit only sees admin events,
templates standardize by copying, admins are blind to boards they don't own,
and board duplication forks permissions silently — all verified from their
own docs and forums. Frame's equivalents (one compiled ABAC evaluator, typed
audit classes with trimmed deltas, reference-based org Blueprints, a catalog
with an exposure register) are exactly the mechanisms that fix those seams,
and the evaluator/writer/audit trio already exists in code.

**Where the mechanism is refused on purpose.** Resource management (N11),
workdocs (N1), an embedded BPMN-grade workflow designer (N3), seat-model
guest editing (N7), and a third-party app marketplace (N12/no-per-Blueprint-
code). In each case the user outcome either belongs to a sibling platform
(Workspace, Workflow Studio, Prism) or is served by Frame's own composition
model. None of the four CLAUDE.md forbidden patterns is needed to match any
Monday capability — their client is served by their own API tier, and
nothing here tempts a per-Blueprint router.
