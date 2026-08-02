# Competitive analysis — output templates

All four files start with the same header block:

```markdown
> Analysis date: YYYY-MM-DD · Analyst: Claude session for <user>
> Sources fetched this session:
> - <url or cloned-repo path> (fetched YYYY-MM-DD)
> - …
> Shelf life: pricing/changelog claims stale after ~1 quarter.
```

## 01-profile.md

```markdown
# <Product> — product profile

<header block>

## Summary
Company, founding/size/funding if public, target market, GTM motion
(self-serve vs sales-led), one-paragraph what-it-is.

## Positioning statement (extracted, not invented)
For [target customer] who [need], <Product> is a [category] that
[key benefit]. Unlike [alternative], <Product> [differentiator].
Source: <homepage/docs URL>.

## Claimed USP (verbatim quotes)
- "…" — <url>

## Feature inventory
| Area | Feature | Evidence | Source |
|---|---|---|---|
| Automation | Rule-based triggers | [verified] docs walkthrough | <url> |
| AI | "AI-powered insights" | [marketing] homepage only | <url> |

## Pricing & packaging
| Tier | Price (billing basis!) | Gating |
|---|---|---|

## Trajectory (from changelog, last 6–12 months)
What they're investing in; 3–6 bullets, each citing a release note.
```

## 02-differentiators.md

```markdown
# <Product> — defensible differentiators

<header block>

## D1: <name>
- **Claim:** "…" [marketing] — <url>
- **Verified capability:** what the docs/code/reviews actually show — <source>
- **Rating:** Strong | Adequate | Weak
- **Defensibility:** why it would survive a bake-off (moat type), or why not
(3–5 of these. Discarded candidates go in a short "Crowded claims set aside"
list at the end, one line each, so the pruning is visible.)
```

Rating scale (from the upstream competitive-brief skill):
**Strong** — market-leading, deep, well-executed. **Adequate** — functional,
undifferentiated. **Weak** — exists but limited. **Absent** — doesn't exist.

## 03-gap-matrix.md

```markdown
# <Product> vs Frame — gap matrix

<header block>

Status legend: superior · partial · absent · planned (PRD-only) ·
blocked by design (see SKILL.md for definitions)

| Their feature | Frame module / PRD | Status | Evidence |
|---|---|---|---|
| Rule automations | specs/frame-prds/04-prd-automation-and-workflow.md | planned (PRD-only) | no hits in src/, no router in functions/api/routers/ |
| Live row sync via client listeners | server-mediated rooms (CLAUDE.md break #3) | blocked by design | tools/fitness/ PM-4; outcome achievable via room subscription |

## Reading the matrix
2–4 paragraphs: where Frame is genuinely behind, where "behind" is really
"not yet built but specified", and where the competitor's mechanism is one
Frame refuses on purpose.
```

## 04-opportunities.md

```markdown
# Opportunities — <Product> analysis

<header block>

## Opportunity Solution Tree

Desired outcome: <the metric/wedge this analysis serves>
├── O1 (leverage: high) <opportunity, traced to matrix row / review pain>
│   ├── S1a: extend <module path> to …
│   │   └── Experiment: <cheapest test>
│   └── S1b: <second solution — one solution = not explored enough>
│       └── Experiment: …
├── O2 (leverage: medium) …
└── O3 …

## Ranked list
| # | Opportunity | Named module(s) | Leverage | Why now |
|---|---|---|---|---|

Include: ≥1 remove/simplify play, ≥1 "make their differentiator irrelevant"
play. Nothing that violates the four CLAUDE.md invariants.

## Executive summary (≤5 lines)
Top 3, one line each: opportunity → module → first experiment.
```
