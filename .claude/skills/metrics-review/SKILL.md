---
name: metrics-review
description: Run a Frame measures review — collect every number the repo can produce THIS SESSION (perf harness, payload sizes, test counts, sweep stats, bundle size), compare against the declared budgets, and produce a scorecard with verdicts and actions. Use for a periodic health review, before/after a performance-relevant change, investigating a regression, or when asked "how are we doing against the budgets".
argument-hint: "[focus area or 'full']"
---

# Metrics Review (Frame)

Adapted from `metrics-review` in
[anthropics/knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins)
(product-management plugin). Upstream assumes a live product with analytics;
Frame is pre-launch, so the adaptation inverts the sourcing: **every number
is measured by running something in this repo during the review** — nothing
is pulled from memory, a dashboard, or a previous session. The
adoption-metric layer (vision §8) is tracked as *defined but not yet
measurable*, honestly, until there is an estate to count.

## Ground rules

1. **Measured-this-session only.** A number without the command that
   produced it (and its date) does not go in the scorecard. Same rule as
   competitive-analysis's live-evidence rule, for the same reason.
2. **Budgets come from the specs, not from vibes.** The authoritative
   sources: `00-prd-index.md` "Cross-cutting non-functional requirements"
   (grid <100ms perceived at 10k rows, view open <1.5s p95, API reads
   <300ms p95 / writes <500ms p95), GR-9 and PRD 02 for grid interaction
   budgets, CD-19 for corporate-data budgets, and vision §10's "10,000 rows
   at 60fps; 50,000 via windowed fetch".
3. **A metric with no action is trivia.** Every red or amber row ends in a
   named action (fix, re-budget with justification, or investigate with an
   owner). Every green row that is green *because nothing exercises it* is
   marked hollow, not green — the fitness suite's own principle.

## What can be measured today (the menu)

| Layer | How (verified commands) |
|---|---|
| Grid interaction & paint | `FRAME_PORT_BACKEND=<port> npx playwright test tools/perf --reporter=line` — budgets asserted in `tools/perf/grid.spec.ts` at 1k/10k/50k rows |
| API latency (local proxy) | `curl -w "%{time_total}"` against `/api/v1/...` endpoints; note local ≠ p95 production and say so |
| Payload sizes | `curl -o /dev/null -w "%{size_download}"` — the catalogue-list regression (2.1 MB → 45 KB) was caught exactly this way |
| Test inventory | pytest / vitest / playwright run summaries (counts are a coverage proxy, not a quality metric — label as such) |
| Fitness invariants | `npm run fitness` — count of enforced vs not-yet-enforced checks (the suite logs pending subjects) |
| Bundle | `npm run build` output sizes |
| Corporate catalogue | sweep stats from the catalogue root doc (dimensions/facts/open counts, quarantined list) |
| Warehouse cost posture | per-query `maximum_bytes_billed` presence — grep `functions/lib/corporate/` (design-time check until real billing exists) |
| Adoption (vision §8) | **Not yet measurable** — "% of corporate-entity columns holding a key vs typed text" needs live registers. Keep the row, mark it, never fake it. |

## Workflow

1. **Scope**: full review or a focus area; if triggered by a change, capture
   the before/after pair or say plainly that no "before" exists.
2. **Confirm the environment**: backend + emulator up, which port
   (`config/ports.json` is the source of truth; the backend may be on an
   override — check before measuring, a wrong-port measurement is a
   measurement of nothing).
3. **Measure** from the menu; paste the actual command output fragments into
   the working notes.
4. **Scorecard** — write `specs/metrics/<date>-review.md`:

```
# Measures review — <date>
Environment: <ports, seed size, machine note> · Trigger: <why now>
| Metric | Budget (source) | Measured | Method | Verdict | Action |
|---|---|---|---|---|---|
Verdicts: green / amber / red / hollow (green but unexercised) / n/a-yet
## Movements since last review   — requires reading the previous file; if
                                   none exists, say "baseline review"
## Actions                        — owner + where it lands (backlog/PRD/fix)
```

5. **Land the actions** (same landing rule as synthesize-research): red
   items become fixes or backlog entries now, not intentions.

## Gotchas
- **Local latency flatters.** The 300ms p95 API budget is a production
  claim; a local 40ms proves nothing about it. Record local numbers as
  regression tripwires, not budget compliance.
- **Playwright perf budgets are deliberately generous** (the spec says so:
  anti-flake, not policing milliseconds). A pass means "no gross
  regression", not "meets GR-9" — say which.
- **Seed size changes invalidate comparisons.** Record `FRAME_SEED_ROWS`
  with every grid measurement.
- The first review is the baseline; resist the urge to editorialize trends
  from n=1.
