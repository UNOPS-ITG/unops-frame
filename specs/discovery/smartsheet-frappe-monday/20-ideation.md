# Ideation: "a Blueprint is an application you can adopt"

> Phase 3 of the smartsheet-frappe-monday discovery run, 2026-08-02.
> Inputs: `10-synthesis.md` clusters A (application loop), C (adopt-with-
> overlay), B (governance visible). Mode: pipeline straight-through — the
> divergence and the sparring are on paper, per the product-brainstorming
> skill; walls (forbidden patterns, N1–N12, wedge test) applied inline.

## Cluster A — the application loop (forms → workflow → automation)

Seven approaches, forced across scope/layer/posture:

**A-1. Three parallel workstreams per PRD.** Build PRD 03 forms, PRD 04
automation, PRD 04 workflow execution as siblings, each to spec. *Honest
but wrong-shaped: highest cost before anything is demonstrably an
application; exactly how Smartsheet's stack accreted into separately-gated
features.*

**A-2. The application spine (vertical slice).** One pilot register runs
the whole loop end-to-end at minimum depth: generated form (with one child
section) → row lands with workflow state → role-gated transition → recipe
fires (assign + notify) → activity visible. Thinnest possible each; prove
the loop before deepening any leg. Serves the Phase-1 pilot criterion
directly (vision §9: "at least one with line items").

**A-3. Steal from the estate: event-contract-first.** Build the automation
engine as a consumer of the already-built rows outbox
(`functions/lib/rows/outbox.py`), actions in the closed vocabulary calling
back through the API — the Workflow Studio graduation shape (vision
appendix) from day one, and the fitness rule (consumers refetch under
their own identity) exercised from the first recipe. Estate prior art:
Workflow Studio's event contract; Bob's connector pattern for the notify
actions.

**A-4. Inversion.** What would make Frame worse at this: each leg with its
own condition language — form logic in one syntax, automation conditions
in another, workflow transitions in `safe_eval` strings (Frappe's actual
shape), permissions in a fourth (Smartsheet's actual shape: forms logic,
automations and Dynamic View configured in three unrelated places).
Reversed: **the loop is one grammar wearing four UIs.** A leg may only
ship if its conditions are shared-grammar ASTs (`functions/lib/grammar/`),
which is already the letter of the index's shared-grammar definition —
the inversion converts it from doctrine into the design center: authoring,
validation (`analyse.py`), steward review and AI assist are built once.

**A-5. Removal.** No form designer, and no automation canvas — ever. A
form is *generated* from Blueprint metadata (field order, sections from
child collections, logic from BP-3a conditional properties); the "form
builder" is the Blueprint editor the user already has. Recipes are a
code-first gallery (config, not canvas) plus a sentence-style picker;
flowchart ambition graduates to Workflow Studio (N3). This deletes two
entire authoring surfaces from the backlog and keeps the closed
vocabulary honest (N5) — the house pattern (no-aggregation fence, closed
action vocabulary) applied twice more.

**A-6. AI-first authoring.** The primary authoring path is natural
language (PRD 08 native assist): "intake form for partner requests with
line items; when amount > 50k, route to category lead" emits Blueprint
delta + generated form + recipe records as reviewable metadata. Leapfrogs
Monday's menu-driven builder precisely *because* of A-4: one grammar means
one target for generation, and review-before-persist keeps it native-tier
(N4 respected).

**A-7. The composed application as the unit.** Pull PRD 10 forward:
what ships isn't loose features but "application templates" — Blueprint +
views + form + recipes + roles packaged as one catalog entry a team
adopts whole. The full reframing destination; also the biggest bite, and
it presupposes A-2's loop existing first.

**Wedge check:** A-2/3/4/5 pass strongly — governance/metadata is exactly
what makes the loop better than a spreadsheet (the form validates against
the Blueprint, the transition is role-gated by the one evaluator, the
recipe is auditable data). A-1 fails the sequencing test, A-7 is the
right destination one step too early.

**Surviving shape: A-2 built the A-3 way under the A-4 rule with A-5's
removals, A-6 as the authoring accelerant, A-7 deferred to the catalog
step (cluster C).**

## Cluster C — adoption without forking

**C-1. Overlay document (Property Setter analog, governed).** A separate
overlay doc per adopting team, merged at compile time
(`blueprint/compile.py`). Most faithful to Frappe; heaviest new concept.

**C-2. `extends` on the existing tier machinery.** A team-tier Blueprint
declares `extends: <catalog id>` with additive-only deltas; reuses Tier
enum + store; the compiled result is base + delta. Cheapest spec, no new
document kind.

**C-3. Removal (rejected).** No overlay; make promotion so fast that
variation flows upstream as new versions. *Dies on the evidence: Frappe's
twenty years say sites need local diffs; a steward gate in every loop
recreates the slow-gate bypass (vision risk #2).*

**C-4. Inversion.** Worse: free local edits to adopted org Blueprints —
Monday's board-duplication sprawl, verified in their own forums. Reversed:
a **legality vocabulary** for overlays — add fields, relabel, defaults,
view defaults; *never* permission rules, never type changes, never
removals — validated at save exactly like Frappe's fieldtype-change
guards, enforced by a fitness test ("overlays cannot weaken permissions").

**C-5. Steal from the estate.** The steward's AI-assisted promotion review
(vision §3) already diffs a candidate against the catalog; overlays give
it a second job — an overlay that many teams independently converge on is
a *promotion signal* ("6 teams added a `region` field; fold it into the
base?"). Adoption telemetry becomes the catalog's growth loop.

**C-6. Package-level adoption.** The adoptable unit is the cluster-A
application (Blueprint + form + recipes + views); overlay applies to the
package (e.g. relabel + one extra field + swap a notification target).
This is A-7 landing in its right place: the catalog entry *is* the app.

**Surviving shape: C-2 + C-4's legality vocabulary + C-5's convergence
signal, with C-6 as the stated destination.** Spec-first (PRD 01
amendment) before code.

## Cluster B — governance visible (the wedge demo layer)

Less divergence needed — the server side exists; this is exposure work.
Five moves, roughly ranked by cost:

**B-1.** Decision trace: `evaluate_row` already computes rule/specificity
to pick which deny to report, then discards it — flag-gate returning it.
**B-2.** Simulate-as-user on the generic blueprints router (never a
per-Blueprint route), rendered for Ingrid. Frappe's dual-path ABAC
*cannot* build this; ours can — the make-irrelevant play.
**B-3.** Render the trim: GR-6 restricted stubs + "N not visible to you"
counts in `src/grid/cells.ts`, fed by trim metadata the API already
returns. The anti-Dynamic-View demo.
**B-4.** Steward estate page over `blueprint/store.py` (tier, owner,
exposure, adoption) — the view Monday admins verifiably cannot get.
**B-5.** GOVERNANCE audit feed (class already defined in
`rows/audit.py`).

**Removal note (B's own inversion):** no separate "admin data model" —
every one of these renders the *same* Decision/Annotation objects the
product already computes (PM-5 machine-readable annotations). If a
steward surface ever needs data the evaluator didn't produce, that's a
second implementation knocking (N8) — refuse it.

## Assumption testing — the direction that wins

**Direction:** the application spine (A-2/3/4/5) + overlay spec (C-2/4/5)
+ trim-and-trace rendering (B-1..B-4), sequenced spine-first.

| # | Assumption | Confidence | Evidence | Would disprove |
|---|---|---|---|---|
| 1 | The closed action vocabulary + shared grammar can express the pilot registers' real intake/workflow/automation needs without scripting (≥80%) | **Low-medium** | None yet — AU-3 vocabulary never confronted real needs; Monday/Frappe both buckled here (metered builder; Server Script) | Pilot needs demanding loops, arbitrary HTTP, or cross-row scripting |
| 2 | A non-developer (Daniel) can author transitions/recipes through grammar-backed UI without it becoming developer-shaped | Medium | Grammar exists; sentence-style recipe UX is proven viable (Monday D1); Frappe's failure was Python-shaped conditions, which A-4 removes | Pilot Daniels needing Kofi for every rule |
| 3 | Generated forms (no designer) are acceptable | Medium | Frappe generates forms from metadata at 700-DocType scale; nobody in the field does child sections at all, so the bar is low | Pilot rejecting field-order/section control as insufficient |
| 4 | The application loop moves adoption more than grid polish (the reframing itself) | Medium — owner directive + three-way market evidence (amputation seam, 87% app attach, ERPNext) | Indirect | Pilot feedback caring only about grid ergonomics; loop features unused |
| 5 | Overlay legality is mechanically checkable at compile time | High | Frappe's guards prove the class; Frame's compile step exists | Legality needing runtime context |
| 6 | The outbox→consumer path can carry automation latency users expect ("instant" notify) | Medium | Outbox built; no latency data | p95 event→action beyond a few seconds on the emulator stack |

**Riskiest (the idea-killer): #1.** If the closed vocabulary can't cover
real needs, Frame forks into Frappe (write code) or Monday (open builder +
meters) — both walls (N5, and the graduation ladder loses its rung).

**Cheapest test:** the **paper catalog** — zero code, ~a day. Take the
three pilot registers' actual intake/workflow/automation needs (they exist
as spreadsheet workarounds today); express every one on paper as
generated-form + transition + recipe records in the closed vocabulary.
Pass: ≥80% expressible; each failure classified as "vocabulary gap
(code-first addition)" vs "genuinely Workflow Studio-shaped" vs
"scripting-shaped (refuse, N5)". This generalizes the Monday agent's S1a
experiment to the whole loop and *precedes any engine code*. Assumption
#6 gets its number from a one-file spike off the existing outbox in the
same session.

## The opponent's round (strongest case against, argued honestly)

*"This re-derives Frappe's roadmap on a half-built grid. GR-1 keyboard
model, fill, clipboard, real-time — all missing. Ship an application layer
over a grid nobody loves and you get ERPNext: powerful, adopted only by
mandate, and Maya still lives in Sheets. Smartsheet won adoption with the
grid; the vision's original risk statement — 'the grid is the product' —
was right the first time."*

Response, conceding what's true: the grid *is* the adoption surface, and
cluster D (perf harness, reference rollups) stays live as table stakes —
nothing here reallocates grid work to zero. But the objection proves the
reframing rather than refuting it: a pilot register without intake, state
and notification **cannot replace its spreadsheet at all** — the
spreadsheet's real job was never the grid, it was the workflow smuggled
into columns ("Status", "Sent to", a date somebody eyeballs). A prettier
grid over the same smuggled workflow is exactly the "has not served us
well" outcome. And the ERPNext comparison mis-lands: ERPNext is unloved
for *authoring* (developer-shaped), which A-4/A-5/A-6 exist to fix — the
loop authored in sentences and generated forms, not Python. The
concession with teeth: **the spine must land inside the pilot registers'
grid experience** — the form is reached from the grid, state renders as a
column, the recipe's effect shows in the activity drawer — never as a
separate "applications" module. If the spine ships as a sibling app,
the opponent wins.

**Runner-up and why it lost:** B-first ("governance visible" as the next
build) — cheapest, deepest built advantage, and the best demo. Lost
because it changes what stewards *see*, not what Maya and Daniel can
*do*; it rides along as the demo layer (B-1..B-4 are days, not weeks,
and B-3 was already Milestone-1 exit criteria territory). D-first (grid
polish) lost on the owner directive plus all three competitors' evidence
that grid-without-stack is a table, not a platform.

## Checkpoint (per pipeline rule 3)

- **Chosen direction:** the **application spine** — one pilot register
  through form → state → recipe end-to-end, event-first on the outbox,
  every condition a shared-grammar AST, forms generated not designed,
  recipes as a code-first gallery; plus the **overlay spec** (PRD 01
  amendment, additive-only legality) and the **governance render layer**
  (trace, simulate-as-user, trimmed-grid stubs, estate page).
- **Runner-up:** governance-visible-first (lost: demos over doing);
  grid-first (lost: directive + evidence).
- **Riskiest assumption:** closed vocabulary covers ≥80% of real pilot
  needs. **Cheapest test:** the paper catalog against the three pilot
  registers, before any engine code; outbox latency spike alongside.
- **Parked, with reasons:** A-7/C-6 packaged-application catalog entries
  (right destination, needs the spine and overlay first — revisit when
  both exist); Gantt depth (Smartsheet's moat, stays P2); marketplace/
  third-party runtime (refused, N12 — PRD 10 stays composition-only);
  per-team usage attribution dashboard (real but small — PRD 08
  amendment note, not a workstream).
