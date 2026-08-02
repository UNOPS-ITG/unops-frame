---
name: roadmap-update
description: Create or update Frame's Now/Next/Later roadmap with statuses derived from evidence in the repo — code greps, test runs, PRD coverage, GCP blockers — never from memory. Use when reprioritizing, absorbing new information (a review, a directive, a blocker landing or lifting), checking "where are we", or building the roadmap view fresh.
argument-hint: "<what changed, or 'refresh'>"
---

# Roadmap Update (Frame)

Adapted from `roadmap-update` in
[anthropics/knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins)
(product-management plugin). Upstream's Now/Next/Later framing survives (it
is the right format here precisely because it avoids false date precision —
Frame has no sprint calendar). The adaptation: Frame's roadmap is
**derived**, not asserted. The repo already contains the truth in five
places; the roadmap's job is to reconcile them into one honest view.

## The five sources of truth (read all, every update)

1. **Vision §9 phasing** (`specs/frame-prds/product-vision-frame.md`) — the
   strategic P1/P2/P3 allocation. The roadmap never contradicts it silently;
   a conflict is surfaced as a decision for the user.
2. **The PRD set** (`00-prd-index.md` + per-PRD phase tags) — what "done"
   means per area.
3. **The codebase** — what is actually built. Statuses are earned by
   evidence: grep + the test suites, exactly like competitive-analysis's
   gap-matrix discipline.
4. **`specs/frame-prds/gcp-provisioning.md`** — external blockers, each with
   what it blocks. Blocked items carry the item number (e.g. "blocked on
   provisioning #5, the floor principal").
5. **Working backlogs** — `specs/ux-refresh.md` (and its status section),
   `.claude/plans/*` milestone plans, `README.md`'s "not yet built" list.

## Statuses (use exactly these)

- **shipped** — built, tested, pushed; cite the suite that covers it
- **in progress** — partial in code; cite files
- **next** — specified, unblocked, not started; cite the PRD ids
- **later** — specified for P2/P3, or deliberately deferred; cite phase tag
- **blocked** — cite the gcp-provisioning item or the external dependency
- **cut** — removed with a reason; cut items stay listed for one update
  before deletion, so a cut is a visible decision rather than a quiet edit

## Workflow

1. **Determine the operation**: refresh / add item / reprioritize / absorb a
   change (blocker lifted, review landed, directive received). For
   reprioritization, ask what changed if it is not in the message — a
   reprioritization without new information is churn.
2. **Re-derive statuses** for every touched area (and spot-check three
   untouched ones — drift hides in the rows nobody edits). Evidence rules:
   "shipped" requires a green test you ran or a suite result from this
   session; "in progress" requires file paths; never promote on memory.
3. **Write `specs/roadmap.md`**:

```
# Frame roadmap
Updated <date>. Derived from: vision §9, PRD set, codebase, gcp-provisioning,
working backlogs. Statuses are evidence-backed; see conventions in the
roadmap-update skill.

## Now      — committed, active. One goal sentence per item + status + evidence
## Next     — unblocked and specified; ordered; each cites its PRD ids
## Later    — P2/P3 and deferred; grouped by PRD area, no false ordering
## Blocked  — item ↔ blocker (provisioning # / external) ↔ what lifting it unlocks
## Changes this update   — added / moved / cut, one line each, with the why
```

4. **Reconcile outward**: if the update changes what `README.md`'s "not yet
   built" or `ux-refresh.md`'s status says, update those in the same commit —
   two documents disagreeing about status is worse than either being stale.

## Prioritization (when asked to rank)

Frame's leverage rule (from competitive-analysis phase 4): impact on the
wedge — *governed, metadata-defined work platform* — ÷ effort, weighted
toward what is already partial. Tie-breakers, in order: unblocks a vision §8
metric; exercises an invariant that currently passes hollow; reduces the
distance to the M1 demo claim ("two people, one URL, different rows").
RICE/ICE are available if the user wants scores, but a ranked list with
reasons beats a spreadsheet of invented reach numbers at this stage.

## Gotchas
- **"Planned (PRD-only)" is a strategic fact, not a gap** — most of Frame's
  surface is deliberately spec-first. A roadmap that reads as "mostly not
  built" is accurate and fine; do not inflate statuses to make it look
  better.
- **Blockers rot in both directions.** Check whether a provisioning item has
  quietly been satisfied before repeating "blocked".
- The vision's phases are strategy; the roadmap is logistics. When the user
  wants to pull a P2 item into Now, that is allowed — record it in Changes
  with the trade, and flag if it needs a `/write-prd` phase-tag amendment.
