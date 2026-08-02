# Smartsheet vs Frame — gap matrix

> Analysis date: 2026-08-02 · Analyst: Claude session for tushard@unops.org
> Sources fetched this session: see `01-profile.md` header (same source set);
> Frame evidence from repo greps/reads this session (paths cited per row).
> Shelf life: pricing/changelog claims stale after ~1 quarter.

Status legend: superior · partial · absent · planned (PRD-only) ·
blocked by design (see SKILL.md for definitions)

Frame's built surface today (verified this session): the grid
(`src/grid/FrameGrid.tsx`, `cells.ts`, `FilterBuilder.tsx`), register pages
(`src/registers/`), saved views (`functions/api/routers/views.py`,
`functions/lib/views/`), rows pipeline (`functions/lib/rows/`: reader, writer,
importer, export, children, audit, outbox, deltas, validate), one permission
evaluator (`functions/lib/permissions/`), the shared grammar
(`functions/lib/grammar/`: parse, evaluate, compile_query, analyse), Blueprint
compile/validate (`functions/lib/blueprint/`), corporate data
(`functions/api/routers/corporate_data.py`, `src/corporate/`). Everything else
is PRD surface — which for a repo this age is the expected shape, not a
failure.

| Their feature | Frame module / PRD | Status | Evidence |
|---|---|---|---|
| Grid editing surface (table view: autosave, real-time, sort/filter) | `src/grid/FrameGrid.tsx`, `src/grid/cells.ts`, `src/grid/FilterBuilder.tsx`; PRD 02 GR-1..GR-4 | partial | Grid + typed cell renderers + filter builder built (`src/grid/` — FrameGrid 486 lines on Glide Data Grid, `glideTheme.ts`); GR-1 keyboard model, GR-2 fill/clipboard-interop, GR-8 real-time not yet demonstrable in code (no realtime tier in `functions/`) |
| 50k rows via large-scale sheets — at the cost of disabling reports/workflows/forms-editing/search/API (help 2483463) | GR-9 (50k windowed fetch, all capabilities intact); `functions/lib/rows/reader.py` (PageRequest/cursor paging built) | partial | Server-side paging exists (`reader.py: PageRequest, read_page`); the 10k@60fps + 50k windowed budget and CI perf harness (GR-9) not yet built. Their trade-off is Frame's sharpest attack seam — see reading below |
| Row hierarchy (indent/outdent, unlimited depth, hierarchy formulas) | GR-3 (hierarchy as declared Blueprint property) | planned (PRD-only) | No hierarchy code in `src/grid/`; GR-3 specifies it P1, declared on the Blueprint rather than as a grid gesture |
| Parent-child line items (their gap: no column type creates child records; forms can't create children; Dynamic View panel shows one row's fields) | BP (parent-child composition), GR-17..GR-19, FM-3; `functions/lib/rows/children.py` | partial → superior by design | Child-row transactional plumbing already exists (`functions/lib/rows/children.py`); master-detail rendering (GR-17) unbuilt. Vision §3: "the one capability unmatched at any Smartsheet price tier" — this session's docs sweep found nothing contradicting that |
| Gantt (dependencies, critical path, baselines) | GR-12 | planned (PRD-only) | Zero Gantt hits in `src/` (grep this session); GR-12 is P2 with dependency types, baselines, critical path specified |
| Board/card view; calendar; timeline | GR-13, GR-14, GR-15, GR-16 | planned (PRD-only) | No view-morphing code in `src/`; GR-16 losslessness matches their "all views synchronized" claim; field-requirement honesty (vision §3) mirrors their own gating (Gantt needs 2 non-formula date columns) |
| Saved views, shared | GR-11; `functions/api/routers/views.py`, `functions/lib/views/model.py` | partial | Built and *permission-trimmed by construction*: "a view carries a query and grants nothing" (`views.py` docstring); filter persisted as AST not string (`views/model.py:73`). Grouping/conditional-formatting in views not yet built (GR-7, GR-20) |
| Dynamic View premium app (row/field access, sold separately, Business+) | PM-2/PM-4 ABAC + GR-6 restricted rendering; `functions/lib/permissions/evaluate.py`, `trim.py` | superior | One evaluator, native, free-with-product vs paid add-on: `compile_rules`/trim built and enforced by `tools/fitness/architecture.test.ts` (PM-4); GR-6 restricted stubs specified. Their mechanism is a second product bolted beside sharing; Frame's is the core model |
| Sharing: 5 item-scoped levels (Owner/Admin/Editor/Commenter/Viewer) | PM-* compiled rules; no per-row grants (N8) | superior (design), partial (build) | Frame's access = compiled ABAC rules, evaluated one place (`functions/lib/permissions/`); item-scoped 5-level sharing has no row/field granularity without paying for Dynamic View [profile] |
| Forms + conditional logic (Business+; When/Then; no child sections) | FM-1..FM-7, FM-2 (logic from BP-3a, declared once); PRD 03 | planned (PRD-only) | No forms code (`grep -ril form src/` hits only unrelated files); FM-3 child sections is the capability their forms lack entirely |
| Update requests to any email; external Guest editors | N7, FM-5/FM-8 magic-link status pages, PM-13 exposure register | blocked by design | Vision N7: no unauthenticated write surface beyond published forms. Their free-Guest-editor model "exists to protect a seat count we do not have" (00-prd-index, Participation). Outcome (external input) achieved via forms + magic links |
| Rule automations (150/sheet, approval/update actions, 250/mo on Pro) | AU-1..AU-3, PRD 04; closed action vocabulary (N5) | planned (PRD-only) | Zero automation code (`functions/consumers/` is empty `__init__.py`); PRD 04 covers triggers/actions/event contract. Their JavaScript premium tier (Bridge) is the N5 anti-pattern Frame refuses |
| Multi-step approvals pausing workflow | AU-* approval actions + BP workflow states; PRD 04, PRD 01 | planned (PRD-only) | Blueprint model has workflow-state metadata (`functions/lib/blueprint/model.py`); no transition engine yet |
| Proofing (annotate/version/approve creative assets) | — (N11) | blocked by design | Vision N11: "no creative proofing… a distinct product category"; no PRD covers it, deliberately. Outcome for document review routes to DG-* + e-signature (PRD 07) where it's a generated-document approval, not creative markup |
| Dashboards (7 widget types, 10-widget Pro cap) | RP-4, RP-5; PRD 06 | planned (PRD-only) | No dashboard code; RP-4 specifies composer with per-viewer trim + PM-5 annotated aggregates — a transparency property their widgets lack |
| Row reports across 30,000 source sheets | RP-1..RP-3; PRD 06 | planned (PRD-only) | RP-1 reports reuse the view engine; RP-2 crosses Blueprints via declared relationships (1 hop) rather than by enumerating source sheets — the need for a 30k-sheet report is itself the sprawl symptom Frame's model removes |
| Cross-sheet references (100 distinct/sheet cap; #INVALID REF breakage; "data links" on roadmap) | BP-9/BP-10 reference-path formulas; `functions/lib/grammar/` | partial | Grammar built (parse/evaluate/compile_query, 329-line evaluator); cross-Blueprint reference resolution planned. Frame refs resolve "through the data model, not sheet coordinates, so they survive restructuring" (vision Pillar 1) vs their documented breakage (community 98919) |
| Cell-anchored formulas | GR-22 non-goal; field-level formulas BP-9 | blocked by design | GR-22: "the single most likely request from a migrating Smartsheet user" — refused with rationale; alternatives are field formulas, rollups, bound Sheets |
| Cell links / DataMesh (scheduled copy sync between sheets, AWM tier) | PRD 14 corporate data; `functions/lib/corporate/`, `src/corporate/`, `functions/api/routers/corporate_data.py` | superior (structural) | Corporate reference plumbing built (routers + `corporate/sql.py` + `CorporatePicker.tsx`). DataMesh is "the foreign key implemented as a scheduled lookup-value copy" (vision §10); Frame binds keys to the warehouse under the reader's identity — a mechanism no external vendor can replicate inside our tenancy (vision §2) |
| DataTable (2M-row external store) | — | absent (deliberate) | Vision §10 explicitly makes no claim against DataTable; volume beyond platform grade routes to the warehouse/Prism (N2, N10) |
| Control Center (portfolio provisioning by folder copy + Global Updates) | BP-15..BP-19 promotion ladder, catalog; PRD 01 | planned (PRD-only) | No promotion code; Blueprint model/versioning exists (`functions/lib/blueprint/`). Their mechanism is distributed copy + patch; Frame's is one versioned Blueprint many teams instantiate |
| WorkApps (role-scoped composed apps, Enterprise) | PRD 10 App Composer | planned (PRD-only) | No composer code; PRD 10 exists; explicitly Phase 3 |
| REST API (Business+ only; untyped cell arrays; dead on large-scale sheets) | Generated envelope client `src/api/client.ts`; generic routers `functions/api/routers/` | superior (design), partial (build) | Client generated from OpenAPI (CLAUDE.md break #2); typed envelope + dynamic payloads; API is not a paid tier and must survive at every scale (vision §3). Fitness enforces no per-Blueprint router |
| Webhooks (custom headers, Jun 2026) | IN-* (PRD 09); allowlisted signed destinations (N9) | planned (PRD-only) | No webhook code; N9 constrains outbound HTTP to allowlisted signed destinations |
| Import/export | `functions/lib/rows/importer.py`, `export.py`; PRD 09 | partial | Both modules exist; Sheets/Excel/Smartsheet-migration tooling (vision §6) not yet |
| MCP server + AI-tool connectors (GA) | AI-* (PRD 08) MCP exposure, permission-evaluated + transparency-annotated | planned (PRD-only) | No MCP code; PRD 08 specifies the differentiated version (typed Blueprints + trim annotations vs their untyped sheet cells — vision Pillar 6) |
| Smart Assist / AI charts / formula generation (tier-gated) | AI-* native assists (PRD 08) | planned (PRD-only) | No AI code in repo; PRD 08 splits native assists vs Playbook |
| Real-time co-editing + presence (table view) | GR-8; server-mediated rooms (CLAUDE.md break #3) | planned (PRD-only) | No realtime tier yet; the *mechanism* is constrained — no client-side row listeners (fitness architecture test), rooms with permission-evaluated subscription |
| Contributor seat economics | No seat licence at all (00-prd-index, Participation) | superior (structural) | Frame has no per-seat price to defend; their Apr 2026 move is a step toward where Frame starts |
| Resource Management | — (N11) | blocked by design | "Smartsheet bought a company for the first" — distinct category, refused |
| Regional residency + CMEK (sheet data only) | Cross-cutting NFRs: our GCP, europe-west, CMEK on Firestore/Postgres | superior (scope), moot (competitively) | Their CMEK excludes attachments/reports/dashboards [CMEK datasheet]; Frame's covers org-tier data wholesale — but vision §10 correctly bars using residency as a buy-argument |

## Reading the matrix

**Where Frame is genuinely behind.** The view system. Smartsheet ships seven
view types with a Gantt that has had two decades of edge-case investment;
Frame has one grid and zero view morphing (GR-12..16 all unbuilt). Same for
automations, forms, dashboards and reports — entire PRDs (03, 04, 06) with no
code behind them. Real-time co-editing is now table-stakes (their table view
has it; Frame's GR-8 doesn't exist yet). None of this is surprising for the
repo's age, but the bake-off honesty is: today Maya gets a register grid with
saved trimmed views, import/export and corporate pickers — not a work
management product.

**Where "behind" is actually "specified and better."** Permission trimming is
the standout: what Smartsheet sells as a separate premium app (Dynamic View)
is Frame's already-built core path — one evaluator, trim on every read, views
as lenses — with fitness tests keeping it that way. The API design (typed
envelope, generic routers, no tier gate) and the no-seat participation model
are the same shape: their weaknesses are load-bearing revenue mechanics, which
means they cannot copy Frame's answer without cannibalizing attach revenue.

**Where their mechanism is refused on purpose.** Proofing and resource
management (N11), guest editors (N7), cell formulas (GR-22), free-form
outbound HTTP and row moves (N9), and script-bearing automations (N5). Each
has a stated alternative outcome path in the matrix. The one to watch is
GR-22: migrating Smartsheet users will ask for cell formulas within the first
week, and the PRD already predicted that.

**The strategic seam.** Their re-platforming buys row count by amputating the
platform — 50k rows costs them reports, most workflows, form editing, search,
mobile and the public API (help 2483463). Frame's GR-9 budget promises the
opposite trade. Since their roadmap says 100k rows "and beyond", the window in
which "every capability intact at 50k" is a demonstrable differentiator is
open now and will narrow as they re-platform feature by feature.
