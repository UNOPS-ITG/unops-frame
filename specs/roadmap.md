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

- **The paper catalog** — express every intake/workflow/automation need of
  the three pilot registers as AU-1 records on paper; ≥80% must fit the
  closed vocabulary. *next* (PRD 04 open question 4; owner + pilot teams;
  one day, zero code). Gate: no `functions/lib/automations/` code before
  this answers. It is the discovery run's riskiest-assumption test.
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

1. **Automation engine + starter recipes** — AU-1..AU-7 execution over the
   shipped outbox, then AU-14's code-first gallery; AU-15 self-approval
   default from day one. Enters Now when the paper catalog passes.
   (PRD 04; `functions/lib/rows/outbox.py` shipped, engine absent.)
2. **Workflow transitions executing** — AU-10 state machine over the
   existing WorkflowState/Transition metadata, conditions as grammar ASTs.
   (PRD 04; metadata shipped in `blueprint/model.py`, engine absent.)
3. **Catalog + overlay implementation** — BP-15/BP-16 tiers and promotion
   skeleton, BP-19 bind-not-copy with the overlay merge in
   `blueprint/compile.py`, BP-27 convergence report. The steward estate
   view rides on this. (PRD 01; spec complete, no tier/catalog code.)
4. **GR-9 performance harness at 50k** — table stakes under the
   reframing, kept because the competitive window ("every capability
   intact at 50k rows") is open now and Smartsheet's roadmap closes it.
   (`npm run perf` exists and asserts 50k responsiveness; the measured
   CI budget harness per GR-9/PRD 11 does not. Not re-run this session.)
5. **Reference-path formulas + rollups** — BP-9a/BP-10 over the shipped
   grammar; shared substrate with the automation conditions. (PRD 01.)
6. **Fitness tripwires for the refusals** — no per-row-grant primitive,
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
- **App Composer** (PRD 10, P3) — with open question 4 live: whether an
  AC-6 template slice pulls to P2 so the spine ships packaged. Owner
  decides; vision §9 change if yes.
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

## Changes this update

- **Created** this file (first edition) from the five sources.
- **Absorbed** the discovery run: PRD amendments AU-14, AU-15, PM-14,
  BP-27, AI-12, AI-13; PRD 04 anti-metering; PRD 10 marketplace refusal
  + phasing question; corrections to the Frappe analysis record.
- **Added to Now**: the paper catalog (riskiest assumption first), the
  forms leg, the governance render layer — the application-spine
  direction per the owner's reframing (`00-scope.md` Reframing section).
- **Demoted**: grid polish from thesis to table stakes — GR-9 harness
  stays at Next #4 on competitive-window grounds, ux-refresh Tier 2
  items continue as hygiene, but the "grid is the product" framing no
  longer drives ordering. Vision §10 amendment proposed in
  `30-handoff.md`, not applied — owner's call.
- **No cuts** this update.
