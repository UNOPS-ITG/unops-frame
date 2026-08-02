# Cross-synthesis: Smartsheet × Frappe × Monday.com vs Frame

> Analysis date: 2026-08-02. Inputs: `specs/competitive/{smartsheet,frappe,monday}/02..04-*.md`
> (all gates satisfied; evidence caveats carried from each profile header).
> Weighting per the owner reframing in `00-scope.md`: the Frappe leg is the
> primary axis; application-completeness outranks grid polish.

## 1. The market's shape

### Where all three agree — crowded ground

Every one of these is claimed by all three competitors and verified as real
in at least two. Frame meets each cheaply from its metadata core or rejects
it citing an N-number; none is a differentiation opportunity.

| Crowded capability | Frame's stance |
|---|---|
| Grid/board editing with saved, filtered views | Meet (built: `src/grid/`, `functions/lib/views/`); table stakes, not thesis |
| Automation as trigger/condition/action records | Meet via AU-1/AU-3 — all three validate *automation-as-data*; Monday's recipe UX is the packaging bar |
| Forms with conditional logic | Meet via FM-* — all three ship it; none does child sections (Frame's opening) |
| Dashboards/reports | Meet via RP-*, bounded by N2 (Prism owns analytics) |
| "AI-powered work" + MCP servers | Meet via PRD 08; protocol adoption is table stakes (all three agents discarded it as crowded). The differentiated part is what tools *return*: typed Blueprints + trim annotations |
| External collaboration economics (free seats/guests) | Rejected as a mechanism (N7) — it defends seat counts Frame doesn't have; outcome served by forms + magic links |
| Enterprise trust surface (SSO, CMEK, regions) | Procurable table stakes; vision §10 already bars using it as an argument |

One deeper agreement matters more than any row: **all three monetize or
gate governance and scale as an add-on** — Smartsheet sells Dynamic View /
Control Center / DataMesh on top of semantically empty sheets (+20–50% of
contract value); Monday gates permissions depth, audit and managed
templates to Enterprise tier and meters actions/AI; Frappe gives semantics
away free but gates *behavior* behind per-DocType Python and developer
mode. Nobody in this field ships governance as the data model itself. That
is the open ground Frame's architecture already occupies.

### Where they diverge — the open quadrant

The three products fail in three *different* directions, and the triangle
between them is empty:

- **Smartsheet** has the grid and loses the platform: at 50k rows,
  large-scale mode disables reports, workflows, form editing, search,
  mobile and the API [verified — help 2483463]. Grid without application
  stack degenerates into a table.
- **Monday** has the packaging and loses the semantics: 87% of its
  enterprise accounts install marketplace apps to close gaps [their own
  published number]; item permissions key only off People columns; audit
  sees admin events, not data; templates standardize by copy; admins are
  blind to unowned boards [all verified, several from their own forums].
- **Frappe** has the semantics and loses the audience: metadata genuinely
  yields a full application (ERPNext: ~700 DocTypes), but behavior is
  per-DocType Python in practice (~320 controller files in their own
  repo), ABAC is two hand-synced implementations, and the authoring
  surface is developer-shaped ("not for the light hearted" is their own
  strapline).

**The empty quadrant: full applications generated from metadata, authorable
by non-developers, with governance as the data model.** That is the
reframed thesis — Frappe-grade applications with Smartsheet-grade
approachability — and the three analyses independently confirm no incumbent
occupies it or can move there without breaking its own revenue mechanics
(Smartsheet's premium-app attach revenue, Monday's Enterprise tier and
meters) or rewriting its architecture (Frappe's per-DocType code).

The evidence also explains *why grid-first has not served Frame well*,
in the competitors' own trajectories: Smartsheet is the proof that a
best-in-class grid without a live application stack behind it is not a
platform — their own scale mode demonstrates the amputation. Monday is the
proof the market pays for finished applications, not better boards. The
grid remains the adoption surface and must stay credible (Maya types into
it on day one), but the three-way evidence says the grid is where the
bake-off *starts*, and the application stack is where it is *won*.

## 2. Merged gap view — Frame vs the field

Statuses per the competitive-analysis legend, now weighted by how many
competitors hold the capability.

### The field has it; Frame has PRDs only (the application stack)

The most consequential band. Every entry is held by **all three**
competitors and has **zero code** in Frame — and together they are
precisely "the application":

| Capability | Field evidence | Frame home |
|---|---|---|
| Forms / intake | All 3 (Smartsheet forms, Monday WorkForms, Frappe Web Forms) | PRD 03 FM-* — nothing in `src/` or routers |
| Automation execution | All 3 (rules, recipes, transition tasks) | PRD 04 AU-* — `functions/consumers/` is an empty `__init__.py` |
| Workflow/state engine | All 3 (Frappe deepest: docstatus, role-gated transitions, self-approval block) | PRD 04; `WorkflowState/Transition` metadata exists in `blueprint/model.py`, no engine |
| Reports/dashboards | All 3 | PRD 06 RP-* — no code |
| Notifications | All 3 | PRD 12 — no code |
| Real-time collaboration | All 3 (Frappe's socket-calls-back-into-app is the pattern to copy) | GR-8 / vision §5 — no realtime tier |
| Document/print generation | Frappe + Smartsheet (Monday partial) | PRD 07 DG-* — no code |
| View morphing (Gantt/board/calendar) | All 3 (Smartsheet's Gantt deepest) | GR-12..16 — no code |

A capability all three hold and Frame lacks is a different fact from a
single rival's feature: this band is what "application" *means* to the
market. Under the reframing, the first six rows are the build priority;
Gantt depth (Smartsheet's twenty-year moat) is explicitly the one to
*sequence last* among them, because it is the hardest to match and the
least distinctive when matched.

### Frame is superior — by verified design, partially or fully built

- **One compiled ABAC evaluator** feeding both row evaluation and query
  trimming (`functions/lib/permissions/`, `grammar/compile_query.py`) —
  verified this session against all three: Frappe's is two hand-synced
  implementations (`permissions.py:481` / `db_query.py:1332`), Monday's
  item permissions key only off People columns, Smartsheet's row/field
  access is a paid premium app. This is the core bet, confirmed from
  Frappe's actual source.
- **Child collections as first-class Blueprints** with own rules inside
  the parent ceiling (`rows/children.py`, `permissions/evaluate.py`) —
  none of the three can express it (Frappe delegates child permissions
  wholly to parent; Smartsheet has no child records at any tier; Monday
  has no parent-child at all).
- **Corporate data under the reader's own credentials** (built: 13
  modules in `functions/lib/corporate/`) — structural, not competitive;
  the mechanism no external vendor can replicate inside our tenancy.
  Smartsheet's DataMesh and Monday's connect-boards are both copies.
- **Typed per-Blueprint-version OpenAPI from generic routers** — beats
  Frappe (method listings, not schemas), Smartsheet (untyped cells,
  Business+ gate, dead on large-scale sheets), Monday (metered GraphQL).
- **No seats, no meters** — Monday monetizes action/AI/API quotas;
  Smartsheet just spent 2026 dismantling its own seat friction
  (Contributor GA). Frame starts where they are headed.
- **Data-grade audit model** (typed CHANGE/ACCESS/GOVERNANCE classes,
  deltas trimmed by the same permission Decision) — Monday's audit API
  covers admin events only; Frappe's Version is close (and its
  impersonator attribution is worth stealing).

### Only one competitor has it — instructive singletons

- **Customization overlay surviving upgrades** (Frappe only: Property
  Setter / Custom Field / Custom DocPerm). **The one conceptual gap the
  whole run exposed**: Frame's catalog has no sanctioned way for an
  adopting team to add a local field without forking — Frappe is
  twenty years of proof that shared metadata cores are adopted *because*
  sites can diff without forking. Not planned anywhere in PRD 01.
- **Gantt maturity** (Smartsheet only) — real deficit, deliberately
  sequenced late; a P2 that stays P2.
- **Apps marketplace** (Monday only) — refused; their 87% attach rate is
  read as an admission, and PRD 10 stays composition-only.
- **Per-team AI/automation usage attribution** (Monday only) — small
  genuine hole; no Frame PRD requirement covers usage *visibility*
  (attribution, not billing). PRD 08 amendment candidate.

### Blocked by design — the refusals, now with citations

Guest/external editors (N7), user scripting (N5 — Frappe ships Server
Script *disabled behind a site-config flag*; Smartsheet's answer is a
paid JavaScript tier), per-row grants (N8 — Frappe's DocShare is an
OR-path around the rule system; their forum documents a fail-open User
Permission incident), marketplace runtime (N12), resource management and
proofing (N11), embedded BPMN (N3), cell formulas (GR-22), row moves
(N9). Every refusal now has a competitor-sourced receipt; the analyses
converge that these should be *recorded in the PRDs and enforced in
fitness* rather than remembered.

## 3. Opportunity clusters — merged, deduped, re-ranked

Sixteen opportunities from the three trees merge into five clusters.
Ranking applies the leverage rule re-weighted per the `00-scope.md`
reframing: application-completeness ÷ effort, with survival across all
three analyses as the robustness test.

### Cluster A — The application loop: forms → workflow → automation, generated from metadata *(survives all 3; rank 1)*

Merges: Smartsheet O4 (forms w/ child sections), Monday O1 (recipe-grade
automation), Frappe O3 (grammar workflow conditions + no-self-approval +
impersonation audit). One cluster because the three opportunities are one
capability: a Blueprint that can *receive* work (form, incl. child
sections none of the field offers), *hold state* (transitions on the
shared grammar where Frappe uses `safe_eval` strings), and *act* (closed-
vocabulary recipes over the built grammar and outbox — Monday's packaging
bar, minus their metering). This is the reframed thesis made concrete:
after this cluster, a Blueprint is an *application*, not a grid.
- PRDs: 03 (FM-1..3, FM-7..8), 04 (AU-1, AU-3, AU-3a, transitions), 05
  (impersonation audit), 08 (NL-to-recipe assist).
- Substrate already built: `functions/lib/grammar/` (parse/evaluate/
  compile_query/analyse), `rows/children.py`, `rows/writer.py`,
  `rows/outbox.py`, workflow metadata in `blueprint/model.py`.
- Effort: high in total but each leg is "mostly assembly" on the grammar
  (both the Monday and Frappe agents' words); wedge impact: highest —
  converts the empty quadrant claim from architecture into product.

### Cluster B — Governance made visible: explainability, estate view, data-grade audit *(survives all 3; rank 2)*

Merges: Frappe O1 (decision trace + simulate-as-user — *only* a single-
evaluator architecture can produce a complete trace; Frappe's cannot),
Monday O2 (steward estate view answering their admins' verified blind
spots) + O3 (CHANGE/ACCESS audit vs their admin-events-only API),
Smartsheet O2 (render the trim: restricted stubs + withheld counts vs
paid Dynamic View). The pattern: Frame's deepest built advantage — the
evaluator/trim/audit trio — is currently *invisible*. Pure render/expose
work turns it into what a steward (Ingrid) and a demo audience can see.
- PRDs: 05 (PM-5, PM-7, PM-10, new "every deny explainable" PM-*), 01
  (BP-15..19 estate/catalog surface), 02 (GR-6 stubs).
- Effort: low-to-medium (server side largely built; trace "computed and
  then thrown away today" per the Frappe agent's read of `evaluate.py`).

### Cluster C — Adoption without forking: catalog, promotion, and the overlay *(survives all 3; rank 3)*

Merges: Frappe O2 (adopt-with-overlay — the run's one conceptual gap),
Smartsheet O5 (promotion ladder + corporate binding as the Control
Center/DataMesh irrelevance play), Monday O2's template half (managed
templates standardize by quota'd copies; Frame standardizes by
reference). All three competitors standardize by *copy* (folder copy,
template instances, forked sites); Frame's answer is one governed
Blueprint many teams adopt — but that answer is only adoptable if teams
can overlay locally (extra fields, relabels — never permission
weakening) without forking. Without the overlay, the catalog risks
recreating the sprawl Frame exists to prevent.
- PRDs: 01 (BP-15..19 + new overlay/extends BP-*), fitness test that
  overlays can never weaken permissions.
- Effort: spec-first (PRD amendment + compile.py merge spike); medium.

### Cluster D — The credible grid: scale harness + references that survive restructuring *(survives 1–2; rank 4 — demoted by reframing, kept as table stakes)*

Merges: Smartsheet O1 (GR-9 perf harness; "every capability intact at
50k" — their amputation seam is open now and their roadmap will close
it) and O3 (BP-9/BP-10 reference-path rollups vs their #1 community
pain, the 100-ref cap and #INVALID REF). Under the reframing this
cluster stops being the thesis and becomes insurance: the grid must stay
good enough that the application story gets its audience. Note O3 is
half data-model (reference semantics — application ground) and its
grammar substrate is shared with Cluster A.
- PRDs: 02 (GR-9), 11 (spike protocol), 01 (BP-9/BP-10).
- Effort: harness low; rollups medium.

### Cluster E — Refuse-and-record: citations into PRDs, tripwires into fitness, principles into positioning *(survives all 3; rank 5 — cheapest)*

Merges: Smartsheet O6, Frappe O5, Monday O4 + O5. Zero-to-one-day items:
record the competitor-sourced receipts as rationale on N5/N7/N8/N9/GR-22
in the PRDs; add vacuously-passing fitness tripwires (no per-row grant
primitive, no integer sensitivity band, no cell-formula site, no row-move
endpoint); state the no-metering principle in PRDs 04/12; re-scope PRD 10
to composition-only with the marketplace refusal recorded; add the one
genuine hole as a PRD 08 amendment (usage attribution). Converts this
run's evidence into durable guardrails before migration pressure arrives.

### Checkpoint (per pipeline rule 3)

Top clusters, one line each:

1. **A — Application loop** (forms+workflow+automation from metadata): the reframed thesis made buildable; survives all three analyses; substrate already in repo.
2. **B — Governance made visible** (trace, estate view, audit surface): deepest built advantage, currently invisible; cheap; only possible for a single-evaluator architecture.
3. **C — Adoption without forking** (catalog + overlay): the run's one conceptual gap; without it the ladder forks and the sprawl returns.
4. **D — Credible grid** (perf harness + reference rollups): demoted to table stakes by the reframing; harness is cheap insurance.
5. **E — Refuse-and-record**: near-free; locks the evidence in.

**Ideation focus:** Clusters A + C as one direction — "a Blueprint is an
application you can adopt" — with B as the wedge demo that makes the
governance visible. D's harness and E ride along as cheap P2/P1
hygiene regardless of direction. No synthesize-research findings to fold
in (none supplied, per scope).

Evidence-weight note: Monday docs claims are snippet-verified (support
site 403s); Smartsheet pricing was triangulated from third parties;
Frappe evidence is strongest (read from source at `43666ea`) — which is
convenient, because the reframing leans on the Frappe leg hardest.
