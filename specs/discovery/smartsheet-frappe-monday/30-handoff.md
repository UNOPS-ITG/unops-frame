# Handoff: smartsheet-frappe-monday discovery run

> Pipeline completed 2026-08-02. Phases: scope (with mid-run owner
> reframing) → 3× competitive-analysis (parallel) → cross-synthesis →
> ideation → PRD amendments → roadmap slot.

## The one-paragraph outcome

Three-way research confirmed the owner's reframing from its own evidence:
Smartsheet's platform amputates itself at grid scale, Monday's enterprise
accounts need marketplace apps because boards don't finish the job, and
Frappe proves metadata→full-application works but only for developers.
The empty quadrant — **Frappe-grade applications with Smartsheet-grade
approachability, governance as the data model** — is Frame's reframed
thesis. Reading the PRDs against that thesis produced the run's most
useful surprise: **the application spine is already specified at P1**
(FM-1..3 forms with child sections, AU-1..7 automations, AU-10 state
machines); the deficit is build, not spec. The PRD phase therefore
produced targeted amendments, not a new PRD.

## PRD changes (all amendments; no new PRD; index untouched)

| Id | PRD | What |
|---|---|---|
| **AU-14 (P1)** | 04 | Starter recipe gallery as code-first config — Monday's packaging moat held as records, not capability |
| **AU-15 (P1)** | 04 | No self-approval by default on approvals and transitions — Frappe's verified guard adopted |
| PRD 04 anti-requirements | 04 | **No metering**, with both incumbents' quota models cited; protection is AU-5/NT-10 budgets |
| PRD 04 open question 4 | 04 | The **paper catalog** — riskiest-assumption test (closed vocabulary covers ≥80% of pilot needs), owned by repo owner + pilot teams, due before any automation engine code |
| **PM-14 (P2)** | 05 | Steward simulate-as-principal + full decision trace from the PM-4a evaluator — the capability Frappe's dual-path ABAC can never build |
| **BP-27 (P2)** | 01 | Overlay convergence reporting — the catalog's growth loop over BP-19's existing overlays |
| **AI-12 (P2)** | 08 | NL-to-recipe authoring targeting AU-14's surface; refuses outside the closed vocabulary |
| **AI-13 (P3)** | 08 | Workspace AI/automation usage visibility — attribution, never a meter (closes the one genuine unspecified gap Monday exposed) |
| PRD 10 scope + OQ4 | 10 | Marketplace refusal recorded with Monday's own numbers; open question: pull an AC-6 template slice to P2 (owner decides — vision §9 change) |

`00-prd-index.md` unchanged: no new PRD, no new shared noun.

## Corrections to the research record

The Frappe leg's headline "conceptual gap" (no customization overlay) was
**wrong against the current spec** — BP-19 already specifies bind-not-copy
adoption with tighten-only overlays. Correction notes appended to
`specs/competitive/frappe/03-gap-matrix.md` and `04-opportunities.md`.
The claim was right about code (no overlay implementation exists yet).

## Proposed vision amendment (not applied — owner's call)

The owner's steer ("grid as the focus has not served us well") implies
amending `product-vision-frame.md` §10's first risk. Proposed shape:
replace "**The grid is the product**" with "**The application loop is the
product; the grid is the front door**" — the grid keeps its performance
budgets and adoption-surface status, but the top engineering risk becomes
shipping the specified P1 spine (forms, automations, state machine) inside
the grid experience, because the three-competitor evidence says grids
without application stacks degenerate into tables and boards without
semantics degenerate into marketplaces. §4's pillar ordering and §9's
phasing survive unchanged; PRD 10 OQ4 carries the one phasing question.
Say the word and I'll draft the full edit.

## First build step

1. **The paper catalog** (PRD 04 OQ4) — one day, zero code, kills or
   confirms the direction before `functions/lib/automations/` exists.
2. In parallel (independent of the test): the outbox→consumer latency
   spike, and the B-cluster render work (GR-6 stubs, PM-14's flag-gated
   trace — the evaluator already computes it).
3. Then the spine, in the pilot registers' grid experience — never as a
   separate module (the ideation's binding concession).

## Parked (with reasons)

- **Packaged application catalog entries** (A-7/C-6): needs spine +
  overlay first; PRD 10 OQ4 holds the phasing question.
- **Gantt depth**: Smartsheet's twenty-year moat; stays P2, matched last.
- **Grid perf harness (GR-9) + reference rollups (BP-9a/BP-10)**: cluster
  D, demoted to table stakes — still worth scheduling, not the thesis.
- **Fitness tripwires for refusals** (no per-row-grant primitive, no
  cell-formula site, no row-move endpoint): cheap, vacuously green today;
  a build-session item, not a spec item.
- **SIEM export surface for audit (PM-7)**: specified; build when the
  security team asks.

## Evidence caveats carried forward

Monday: support-site claims are snippet-verified (403 on direct fetch);
enterprise pricing third-party. Smartsheet: pricing triangulated;
approvals rest on snippets. Frappe: strongest leg (read from source at
`43666ea`). Shelf life ~1 quarter on pricing/changelog claims.
