# Frame roadmap

Updated 2026-08-02. Derived from: vision §9, the PRD set, the codebase
(suites run this session: `npm run verify` green — fitness 11/11, unit
27/27, lint, typecheck, ports; backend pytest 518 passed), 
`gcp-provisioning.md`, and the working backlogs (`ux-refresh.md`, the M1
plan). Statuses are evidence-backed; conventions per the roadmap-update
skill. First edition of this file — created to absorb the
smartsheet-frappe-monday discovery run (`specs/discovery/…/30-handoff.md`)
and the owner's reframing: **application completeness over grid emphasis;
the grid is the front door, the application loop is the product.**

## Now

- **The automation engine** — AU-1..AU-7 execution over the shipped
  outbox, with AU-15..AU-17 from day one; then AU-14's recipe gallery.
  *next → unblocked* (the paper catalog **passed** 2026-08-02: 97% of
  automation-shaped pilot needs expressible, zero scripting demands —
  `specs/pilots/paper-catalog.md`; engine code cleared to start).
- **The application spine, forms leg** — generated forms with one child
  section, landing through the existing writer/children path (FM-1, FM-2,
  FM-3, FM-7). *next* (specified P1; substrate shipped: `rows/writer.py`,
  `rows/children.py`, BP-3a in metaschema — backend suite green this
  session). Lands inside the register grid experience, never as a
  sibling module (the ideation's binding concession, `20-ideation.md`).
- **Governance render layer** — PM-14's flag-gated decision trace (the
  evaluator already computes and discards it), simulate-as-user on the
  generic blueprints router, withheld-count polish. *in progress*
  (`functions/lib/permissions/evaluate.py` built and green; trace surface
  not started; grid already renders withheld cells legibly per README).
  Cheap, and it is the wedge made visible.

## Next (ordered)

1. **Workflow transitions executing** — AU-10 state machine over the
   existing WorkflowState/Transition metadata, conditions as grammar ASTs.
   (PRD 04; metadata shipped in `blueprint/model.py`, engine absent.)
2. **Catalog + overlay + application templates** — BP-15/BP-16 tiers and
   promotion skeleton, BP-19 bind-not-copy with the overlay merge in
   `blueprint/compile.py`, BP-27 convergence report, then **AC-7
   application templates (now P2 by owner decision)** — the fleet pilot
   (asset + overlay) is the proof case, and PRD 01 open question 4
   (overlay child collections) must be decided before its template is
   authored. The steward estate view rides on this. (PRDs 01, 10.)
3. **GR-9 performance harness at 50k** — table stakes under the
   reframing, kept because the competitive window ("every capability
   intact at 50k rows") is open now and Smartsheet's roadmap closes it.
   (`npm run perf` exists and asserts 50k responsiveness; the measured
   CI budget harness per GR-9/PRD 11 does not. Not re-run this session.)
4. **Reference-path formulas + rollups** — BP-9a/BP-10 over the shipped
   grammar; shared substrate with the automation conditions, and the
   pilots lean on both (paper catalog C5, P7, A8). (PRD 01.)
5. **Fitness tripwires for the refusals** — no per-row-grant primitive,
   no cell-formula site, no row-move endpoint; vacuously green today,
   tripwires when migration tooling lands. (Cluster E; `tools/fitness/`.)

## Later (grouped by PRD area, no false ordering)

- **Views** (PRD 02, P2): board, calendar, timeline; Gantt (GR-12) is
  deliberately last among view types — the deepest incumbent moat and the
  least distinctive when matched (`10-synthesis.md`).
- **Reporting/dashboards** (PRD 06, P2), **document generation** (PRD 07,
  P2), **notifications** (PRD 12, P1/P2 mix), **search** (PRD 13, P2),
  **realtime rooms** (GR-8, P2).
- **AI layer** (PRD 08): AI-1/AI-2 assists P1 behind the estate gateway;
  AI-12 NL-to-recipe P2; AI-13 usage visibility P3; MCP surface (AI-10)
  P3 — with transparency annotations, the differentiated part.
- **App Composer** (PRD 10): full composer (AC-1..AC-5) stays P3;
  AC-7 application templates moved to P2 (owner decision, see Next #2).
- **Bound Sheets** (IN-7..9, P2/P3), **Smartsheet migration tooling**
  (P3, feeds the O3b/O6 migration-guide plays).

## Blocked (item ↔ blocker ↔ what lifting it unlocks)

- **Corporate `open` fast path** ↔ provisioning #5 (floor principal) +
  #6 (`ROW_ACCESS_POLICIES` read) ↔ mirrored dimensions at grid speed;
  today all 555 swept dimensions correctly classify `entitled`.
- **BigQuery connector end-to-end** ↔ #3 (OAuth client) ↔ any user
  actually connecting; code complete and waiting.
- **Any deployment** ↔ #1 (GCP project), #9 (Firestore `frame` with
  CMEK+PITR at creation), #10 (IAP audience) ↔ anything beyond emulators.
- **Scheduled sweep** ↔ #7 (service account) + #8 (Cloud Scheduler) ↔
  "discovered, not authored" being continuously true.

Nothing in Now or Next is GCP-blocked; the spine is entirely local work.

## Changes this update (2026-08-02, second edition — owner decisions landed)

- **The paper catalog ran and passed** the same day it entered Now:
  44 needs from the four named pilots (contract, asset, project, fleet —
  supplied by the owner), 97% of automation-shaped needs expressible,
  zero scripting demands. `specs/pilots/paper-catalog.md`. The
  automation engine moved from gated to **Now**.
- **Two vocabulary refinements adopted** from the catalog's findings:
  AU-16 computed action parameters, AU-17 sweep-trigger semantics.
- **The vision amendment applied** (owner decision): §10's first risk is
  now "the application loop is the product; the grid is the front door";
  §9 Phase 1 names the four pilots; §9 Phase 2 gains application
  templates.
- **AC-7 application templates specified at P2** (owner decision closing
  PRD 10 OQ4); fleet-as-asset-plus-overlay is the proof case, which
  turned PRD 01 OQ4 (overlay child collections) from hypothetical to
  blocking-before-template-authoring.
- **New open question**: PRD 04 OQ4 (carried-attribute refreshes vs
  `row.updated` triggers), surfaced by pilot need C11.
- **Prior edition** (same day): created the file; absorbed the discovery
  run's amendments (AU-14/15, PM-14, BP-27, AI-12/13, anti-metering,
  marketplace refusal); demoted grid polish to table stakes.
- **No cuts** this update.
