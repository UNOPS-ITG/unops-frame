# Opportunities — Smartsheet analysis

> Analysis date: 2026-08-02 · Analyst: Claude session for tushard@unops.org
> Sources fetched this session: see `01-profile.md` header (same source set);
> Frame evidence per `03-gap-matrix.md`.
> Shelf life: pricing/changelog claims stale after ~1 quarter.

## Opportunity Solution Tree

Desired outcome: **operations teams choose Frame over a Smartsheet sheet for
their next register, because the grid is as good and the platform doesn't
degrade with scale or governance** (vision §8; the wedge is governed,
metadata-defined work at Smartsheet-grade ergonomics).

```
Desired outcome: Smartsheet-grade grid, no scale/governance amputation
├── O1 (leverage: high) "Every capability intact at 50k rows" — their large-scale
│   │   mode disables reports/workflows/forms-editing/search/API (help 2483463);
│   │   their roadmap will close this seam; ours is open now (GR-9)
│   ├── S1a: Build the GR-9 CI performance harness now — extend src/grid/FrameGrid.tsx
│   │   │   + functions/lib/rows/reader.py (windowed fetch already has PageRequest/
│   │   │   cursors) to a measured 10k@60fps / 50k-windowed budget, enforced like
│   │   │   tools/fitness (PRD 11 spike protocol; PRD 02 GR-9)
│   │   └── Experiment: synthetic 50k-row Blueprint; script scroll/edit/filter;
│   │       record p95 interaction latency in the metrics-review harness this month
│   └── S1b: Make the contrast *demonstrable*: one demo register at 50k rows with
│       │   saved trimmed views + import/export + corporate pickers all live
│       │   (src/registers/RegisterPage.tsx over reader.py paging)
│       └── Experiment: side-by-side demo script vs a Smartsheet trial large-scale
│           sheet (their own opt-in flow documents what dies); 1 day, zero build
├── O2 (leverage: high) Native trimmed views as the anti-Dynamic-View — they charge
│   │   Business+ plus a premium app for row/field access; Frame's is built
│   │   (functions/api/routers/views.py, lib/permissions/trim.py) but invisible
│   ├── S2a: Render the transparency annotations in the grid — GR-6 restricted
│   │   │   column stubs and "N not visible to you" counts in src/grid/FrameGrid.tsx
│   │   │   + src/grid/cells.ts, fed by the trim metadata the API already computes
│   │   │   (PM-5, GR-6)
│   │   └── Experiment: two-persona walkthrough (Maya vs Daniel) on one saved view
│   │       URL showing legitimately different rows+columns, annotated — the
│   │       Milestone-1 exit criterion (views.py docstring) made into a demo
│   └── S2b: Ship view-level grouping with annotated aggregate footers (GR-7 +
│       │   PM-5) so the trimmed-aggregate honesty story is visible in numbers,
│       │   extending functions/lib/rows/reader.py group aggregation
│       └── Experiment: one grouped register with a rule withholding rows from one
│           tester; verify footer shows full-set aggregate + withheld count
├── O3 (leverage: high) References that survive restructuring — their 100
│   │   cross-sheet-reference cap and #INVALID REF breakage are top community
│   │   pain (community 127183/139001/98919); their fix ("data links") is roadmap
│   ├── S3a: Implement BP-9/BP-10 reference-path formulas over the built grammar —
│   │   │   extend functions/lib/grammar/ (parse/evaluate/compile_query) and
│   │   │   functions/lib/blueprint/compile.py with one-hop reference resolution
│   │   │   and rollups (vision Pillar 1: refs resolve through the data model)
│   │   └── Experiment: two-Blueprint spike (project ← risks): a rollup field that
│   │       survives renaming fields and re-sorting rows; assert no positional
│   │       coupling anywhere in the persisted AST
│   └── S3b: Migration-shaped proof: importer maps a Smartsheet cross-sheet
│       │   VLOOKUP estate onto reference fields — extend
│       │   functions/lib/rows/importer.py with a link-to-reference mapping report
│       │   (PRD 09 import; vision §6 Smartsheet migration tooling)
│       └── Experiment: export one real internal Smartsheet estate (2 linked
│           sheets) to CSV; hand-map to two Blueprints; count links that became
│           typed references vs strings
├── O4 (leverage: medium) Forms that create real documents — their forms make one
│   │   row, no child sections, and conditional logic is Business-gated
│   │   (help 2481701); Frame's FM-2 logic is declared once on the field and
│   │   FM-3 submits parent+children transactionally
│   ├── S4a: Build FM-1/FM-2/FM-3/FM-7 minimal: form renderer generated from
│   │   │   Blueprint metadata (new src/forms/ consuming src/api/client.ts), child
│   │   │   sections landing through functions/lib/rows/children.py writes
│   │   └── Experiment: one intake register with line items (the Phase-1 pilot
│   │       criterion, vision §9) submitted end-to-end through a generated form
│   └── S4b: Magic-link status page (FM-8) as the governed answer to their
│       │   guest-editor model — read-only, allowlisted fields, no auth
│       └── Experiment: static status page served from a signed token against
│           functions/api/routers/rows.py read path, fields from an allowlist
├── O5 (leverage: medium) Make Control Center + DataMesh irrelevant (the
│   │   "differentiator-irrelevance" play) — both premium apps exist to stamp and
│   │   sync copies; Frame's promotion ladder + corporate binding remove the need
│   │   for copies at all
│   ├── S5a: Ship the promotion ladder skeleton BP-15..BP-19: promote a team
│   │   │   Blueprint to a catalog entry with provenance/credit —
│   │   │   functions/lib/blueprint/store.py + a catalog router (generic, per
│   │   │   CLAUDE.md break #1) + src/app/ catalog page
│   │   └── Experiment: promote one pilot register; verify a second workspace
│   │       instantiates it without copying (one Blueprint version, two tenants
│   │       of rows) — the structural refutation of provisioning-by-folder-copy
│   └── S5b: Position corporate bindings against DataMesh in the one pager the
│       │   demo uses: their own FAQ says DataMesh copies (help 2482785); Frame's
│       │   built corporate picker (src/corporate/CorporatePicker.tsx,
│       │   functions/lib/corporate/sql.py) references under the reader's identity
│       │   (PRD 14)
│       └── Experiment: zero build — a recorded demo: change upstream dimension
│           label, watch Frame row reflect it with staleness marker (GR-4) while
│           the DataMesh story requires the next scheduled copy
└── O6 (leverage: medium, remove/simplify) Refuse the surface they're stuck
    │   maintaining — codify the "not building" list as enforced negatives, so
    │   scope gravity from migrating users can't quietly re-add their weight
    ├── S6a: Add fitness checks for the refusals nearest the grid: no per-cell
    │   │   formula site (GR-22), no client-side row listeners (already covered),
    │   │   no row move/copy-between-Blueprints endpoint (N9) — extend
    │   │   tools/fitness/architecture.test.ts with not-yet-enforced logging per
    │   │   CLAUDE.md convention
    │   └── Experiment: write the checks now while all pass vacuously; they become
    │       tripwires the week migration tooling lands
    └── S6b: Migration guide page mapping each refused Smartsheet feature to its
        │   Frame answer (cell formula → field formula/rollup/bound Sheet; row
        │   move → view filter/state change; guest editor → form/magic link),
        │   sourced from GR-22/N6/N7/N9 rationale text
        └── Experiment: dry-run the guide against the O3b estate migration; count
            questions it fails to answer
```

## Ranked list

| # | Opportunity | Named module(s) / PRD ids | Leverage | Why now |
|---|---|---|---|---|
| 1 | Capability-intact 50k grid, measured | `src/grid/FrameGrid.tsx`, `functions/lib/rows/reader.py` — GR-9, PRD 11, PRD 02 | High | Their large-scale mode amputates the platform *today* (help 2483463) but their roadmap ("100k rows and beyond", data links) closes the seam; the demonstrable window is open now |
| 2 | Transparency-rendered trimmed views (anti-Dynamic-View) | `src/grid/cells.ts`, `src/grid/FrameGrid.tsx`, `functions/lib/permissions/trim.py` — PM-5, GR-6, GR-7, GR-11, PRD 05/02 | High | Server side already built; pure render work turns Frame's deepest structural advantage into the thing a demo audience can *see*, against a paid premium app |
| 3 | Reference-path formulas + rollups over the grammar | `functions/lib/grammar/`, `functions/lib/blueprint/compile.py` — BP-9, BP-10, PRD 01 | High | Their #1 community pain (100-ref cap, broken links) and their fix is still roadmap; Frame's grammar/AST substrate is already in the repo |
| 4 | Generated forms with child sections + magic-link status | new `src/forms/`, `functions/lib/rows/children.py` — FM-1..FM-3, FM-7, FM-8, PRD 03 | Medium | Their forms can't create children at any tier and gate logic to Business+; Frame's Phase-1 pilot needs this anyway |
| 5 | Promotion ladder + corporate binding as the Control Center/DataMesh irrelevance play | `functions/lib/blueprint/store.py`, `src/corporate/` — BP-15..BP-19, PRD 01, PRD 14 | Medium | Their premium-app estate is +20–50% of contract value defending a copy architecture; one promoted Blueprint demo refutes it structurally |
| 6 | Enforced refusals (remove/simplify) | `tools/fitness/architecture.test.ts` — GR-22, N6, N7, N9, IN-12 | Medium | Cheapest insurance: migration pressure predictably asks for cell formulas and row moves; tripwires cost a day while all checks pass vacuously |

Guardrail check: no per-Blueprint routers, no type mirrors, no client-side
access or row listeners, no wire-case transforms proposed anywhere above; O6 is
the remove/simplify play; O5 is the make-their-differentiator-irrelevant play;
every opportunity is tied to a user job (scale without amputation, legible
governed access, references that don't rot, intake with line items, catalog
instead of copies) rather than feature parity — and the deliberate
*non*-responses (no proofing, no resource management, no DataTable answer, no
seat model) are recorded in the matrix as refusals, not gaps to close.

## Executive summary

1. **Prove "every capability intact at 50k rows"** — build the GR-9 perf
   harness over `src/grid/FrameGrid.tsx` + `functions/lib/rows/reader.py`;
   first experiment: scripted 50k-row scroll/edit/filter run recorded in
   metrics-review this month.
2. **Render the trim** — GR-6/PM-5 restricted stubs and withheld counts in
   `src/grid/cells.ts`; first experiment: two-persona one-URL saved-view demo
   against Dynamic View's paywalled equivalent.
3. **Ship reference-path rollups** — BP-9/BP-10 on
   `functions/lib/grammar/` + `blueprint/compile.py`; first experiment:
   two-Blueprint rollup that survives field renames where Smartsheet returns
   #INVALID REF.
