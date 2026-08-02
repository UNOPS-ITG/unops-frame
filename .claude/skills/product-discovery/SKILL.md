---
name: product-discovery
description: The master pipeline — research one or more SaaS products end to end, run the full competitive analysis, brainstorm what Frame should do about it, and finish with a buildable Frame PRD. Orchestrates competitive-analysis, product-brainstorming and write-prd (plus synthesize-research and roadmap-update when they apply). Use when asked to "do the full analysis" of competitor(s), take a market question all the way to a spec, or produce a PRD grounded in competitive research.
argument-hint: "<product(s) to research, and optionally the feature area / question>"
---

# Product Discovery (master pipeline)

One command, four phases, ending in **a Frame PRD you can build from**. This
skill orchestrates; the phase skills do the work — load each one when its
phase starts and follow it fully. Do not reimplement their content here.

```
scope → [competitive-analysis × N products] → cross-synthesis
      → product-brainstorming (grounded) → write-prd → roadmap slot
```

## Ground rules

1. **The phase skills' rules are in force during their phases** — live
   evidence only, `[verified]`/`[marketing]` tags, the four forbidden
   patterns, N1–N12, the landing rule. This skill adds sequencing and
   handoffs, never exemptions.
2. **Every phase ends in a file.** The pipeline's memory is
   `specs/discovery/<topic-slug>/`, not the chat. A later phase reads the
   earlier phase's file, so a phase that only "remembers" its output starves
   the next one.
3. **Checkpoints, not silence.** After cross-synthesis and after ideation,
   surface a compact summary and the decision the next phase will assume.
   Default is to proceed (the user asked for the full pipeline); pause only
   if the next phase would commit to something the evidence genuinely
   underdetermines — e.g. two opportunity clusters of equal weight pointing
   at different PRDs.
4. **Scale honestly.** One competitor ≈ one session's work before the PRD.
   For 3+ competitors, run the per-competitor research in parallel
   (subagents or a Workflow — each produces its own
   `specs/competitive/<slug>/` set independently; they share nothing until
   cross-synthesis). Say what was parallelized.

## Outputs

```
specs/competitive/<competitor-slug>/   # per competitor, from the
  01..04-*.md                          #   competitive-analysis skill
specs/discovery/<topic-slug>/
  00-scope.md          # phase 0
  10-synthesis.md      # phase 2 (cross-competitor; exists even for N=1)
  20-ideation.md       # phase 3
  30-handoff.md        # phase 4 pointer: which PRD, which ids, what's next
specs/frame-prds/…     # the PRD itself lives with the other PRDs, never
                       #   in the discovery folder
```

## Phase 0 — Scope (one file, five minutes)

Pin down and write `00-scope.md`:
- Products to research (1..N) and why each is on the list.
- The question: full-product comparison, or a feature area?
- The decision this informs — for this pipeline it is always ultimately
  "what should Frame build", but note any sharper framing the user gave.
- Optional inputs the user has: raw feedback/research material (if yes,
  schedule a `synthesize-research` pass whose findings feed phase 3), an
  existing PRD this will amend rather than a new one.

## Phase 1 — Research (competitive-analysis, per product)

Load **`competitive-analysis`** and run it fully per competitor — all four
of its phases, all four files, its ground rules verbatim. For multiple
competitors, parallelize per rule 4; each agent gets the scope file and one
competitor.

Gate before proceeding: every competitor has its `04-opportunities.md`, and
each opportunity in it names a Frame module or PRD id. Thin research
produces confident nonsense downstream — if a competitor's evidence is weak
(fetches failed, docs paywalled), record that in the profile and weight it
down later rather than padding it.

## Phase 2 — Cross-synthesis (this skill's own work)

The one step no sub-skill owns. Read every `02-differentiators.md`,
`03-gap-matrix.md` and `04-opportunities.md` and write `10-synthesis.md`:

- **The market's shape**: where the N competitors agree (crowded ground —
  Frame should meet it cheaply or reject it citing an N-number), and where
  they diverge (open ground — the interesting quadrant).
- **Merged gap view**: Frame vs the field, not vs one rival. Keep the five
  gap-matrix statuses; a capability every competitor has and Frame lacks is
  a different fact from one only the weakest has.
- **Opportunity clusters**: merge the per-competitor opportunity trees,
  dedupe, and re-rank by the leverage rule (wedge impact ÷ effort, weighted
  by partial/planned). Note which opportunities *survive all N analyses* —
  those are the robust ones.
- If a `synthesize-research` pass ran, its top findings join the ranking
  here with their evidence weights.

**Checkpoint**: top 3–5 clusters, one line each, and which the ideation
phase will focus on.

## Phase 3 — Ideation (product-brainstorming, grounded)

Load **`product-brainstorming`**. Pipeline mode adapts its conversational
stance: run its solution-ideation and assumption-testing modes *against the
top clusters from 10-synthesis.md*, and write the results to
`20-ideation.md` as you go — divergent options per cluster (its 5–7 rule,
including the inversion and the removal), then the riskiest assumption and
cheapest test for the direction that wins. Its walls (forbidden patterns,
N1–N12, the wedge test) apply with full force; a cluster that dies on a
wall dies here, visibly, not in the PRD.

If the user is present and engaged, this phase is better as the
conversation the skill wants to be — offer that. If running
straight-through, be your own sparring partner on paper: argue the
strongest case against the winning direction before accepting it.

**Checkpoint**: the chosen direction, the runner-up and why it lost, the
riskiest assumption and its test.

## Phase 4 — The PRD (write-prd)

Load **`write-prd`** and follow it fully: amend-before-create, house
requirement style, index integration, cross-reference verification. The
discovery inputs map in directly:

- Purpose/Scope draw on `10-synthesis.md` (the market shape is the "why
  now"); cite competitor evidence sparingly — a PRD argues from the user
  job, not from fear of a rival.
- Requirements come from the chosen direction in `20-ideation.md`; the
  cheapest-test experiment becomes either a P1 requirement or an explicit
  open question with an owner.
- Non-goals get first-class treatment: the clusters that *lost* in phases
  2–3 are exactly the scope creep this PRD will face — fence them with
  reasons (and N-numbers where they apply).
- Phase tags: the riskiest-assumption test and the wedge-critical core are
  P1; everything that merely matches the field is P2 unless evidence says
  otherwise.

Then write `30-handoff.md`: the PRD (or amended ids), what changed in
`00-prd-index.md`, the first build step, and anything parked.

**The first build step is frontend-first** (owner directive, 2026-08-02):
(a) build the frontend of the new surface first; (b) feed it hard-coded
JSON fixtures *shaped like the intended API contract*, so replacement is
mechanical rather than a rework; (c) stop for **vision verification** —
the owner confirms the product *feels* like what they have in mind before
any engine or backend work starts; (d) only then build functionality and
swap fixtures for API shapes as they evolve. A discovery run that hands
off straight into backend build has skipped the cheapest moment to catch
a vision misalignment — which is exactly what a pipeline grounded in
competitor evidence is most at risk of (building what the market has
instead of what the owner means).

## Phase 5 — Close the loop (small, do not skip)

- Load **`roadmap-update`** and slot the new work into
  `specs/roadmap.md` (usually Next; the cheapest test sometimes goes
  straight to Now).
- Offer `/session-planning` for the first build session.
- Commit everything; the pipeline's value is in the repo, not the transcript.

## Failure honesty

If a phase cannot meet its gate (research too thin, every cluster dies on a
wall, the PRD would only restate an existing one), stop the pipeline there
and say so with the artifacts produced — a truncated pipeline with honest
files beats a completed one with hollow ones.
