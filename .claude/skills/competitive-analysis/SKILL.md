---
name: competitive-analysis
description: Run a four-phase competitive analysis of a rival product against Frame — live research (docs, changelog, pricing, OSS repo clone), differentiator synthesis, a codebase gap matrix with file paths, and an Opportunity Solution Tree of ranked opportunities. Use when asked to analyze a competitor, compare Frame with another product (Smartsheet, Airtable, Baserow, NocoDB, Frappe, Retool, …), build a gap matrix, or find where Frame should differentiate.
argument-hint: "<competitor product or feature area>"
---

# Competitive Analysis

Produce a competitor analysis that ends in **concrete, module-level product
opportunities for Frame** — not a generic market brief. Four phases, each with
a file deliverable. Paths in this document are relative to the repo root.

Adapted from the `competitive-brief` and `product-brainstorming` skills in
[anthropics/knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins)
(product-management plugin), specialized for Frame: phase 3 grounds every
claim in this repo's actual files, and phase 4 must respect Frame's
architectural invariants.

## Ground rules (non-negotiable)

1. **Live evidence only.** Every capability claim about the competitor must
   trace to something fetched *this session*: a URL (WebFetch/WebSearch) or a
   file in a repo you cloned. Training memory is a hypothesis, never a source.
   Real example from authoring this skill: remembered Smartsheet pricing was
   roughly half of what the live pricing page said.
2. **Mark every claim** as `[verified]` (seen in docs, changelog, code, or a
   hands-on review) or `[marketing]` (homepage/sales copy only). The split is
   the whole point of phase 2.
3. **Date-stamp everything.** Competitive analysis rots. Every output file
   starts with the analysis date and the list of sources fetched.
4. **Frame context first.** Before phase 3, read
   `specs/frame-prds/product-vision-frame.md` and
   `specs/frame-prds/00-prd-index.md`, plus the PRD(s) covering the feature
   areas under analysis. Also read the "deliberate breaks" section of
   `CLAUDE.md` — it constrains phase 4.

## Outputs

Write to `specs/competitive/<competitor-slug>/` (create it; nothing exists
there until the first analysis runs):

```
specs/competitive/<slug>/
  01-profile.md          # phase 1: product profile + feature inventory
  02-differentiators.md  # phase 2: 3–5 defensible differentiators
  03-gap-matrix.md       # phase 3: their feature ↔ Frame module ↔ status
  04-opportunities.md    # phase 4: ranked Opportunity Solution Tree
```

Templates for all four files: [templates.md](templates.md).

## Phase 0 — Scope (30 seconds, don't skip)

Pin down before researching: which competitor(s) or feature area, and what
decision this informs (PRD prioritization? positioning? parity check?). If
the user gave only a product name, default scope is **full product vs Frame's
PRD surface**, decision context **feature prioritization**. Don't block on
asking if the default is sensible.

## Phase 1 — Research (mandatory live fetching)

Fetch, in order of information density:

1. **Docs / help center** — the feature inventory lives here, not on the
   homepage. WebFetch the docs index, then the 3–6 deepest sections relevant
   to scope.
2. **Changelog / release notes** — trajectory and investment areas. Recent
   6–12 months is enough.
3. **Pricing page** — tiers, gating, packaging model (per-seat vs usage).
   Verified working:
   ```
   WebFetch https://www.smartsheet.com/pricing
     prompt: "List plan tiers, prices, and feature gating"
   ```
4. **Reviews** — WebSearch `"<product> review site:g2.com"` or reddit; what
   users praise/complain about is `[verified]` capability evidence.
5. **If OSS: clone it.** Into the scratchpad, never the repo:
   ```bash
   cd <scratchpad> && git clone --depth 1 https://github.com/<org>/<repo>.git
   ```
   (Verified in this environment; ~5s for a typical repo.) Then read their
   README, architecture docs, and the modules covering the scoped features.
   Code beats docs: a feature in the repo is `[verified]`, a feature only on
   the homepage is `[marketing]`.

WebFetch notes: cross-host redirects are returned, not followed — re-call
with the redirect URL. Marketing sites are SPA-heavy; if a fetch returns
boilerplate, try the docs subdomain instead (`help.`, `docs.`,
`support.`).

**Deliverable `01-profile.md`:** company/product summary, positioning
statement (use the template in templates.md), feature inventory table with
per-row evidence tag + source URL, claimed USP verbatim, pricing/packaging.

## Phase 2 — Synthesis: defensible differentiators

Distill the profile to **3–5 differentiators the competitor could defend in
a bake-off** — not their marketing pillars. For each:

- What they claim (quote it) vs what is verified (cite the doc/code/review).
- Rate the verified capability: Strong / Adequate / Weak (scale in
  templates.md).
- Why it's defensible (or not): data moat, architecture, ecosystem,
  distribution — or just first-mover copy anyone could match.
- Discard "differentiators" every competitor claims (crowded positions:
  "AI-powered", "all-in-one") unless the verified capability is genuinely
  ahead.

**Deliverable `02-differentiators.md`.**

## Phase 3 — Codebase mapping: the gap matrix

For every feature-inventory row that matters to the scope, locate Frame's
answer. Search **both** code and PRDs — Frame is early; most of the surface
is specified but unbuilt, and "planned" is a different strategic fact than
"absent".

Frame's module map (verified 2026-08):

| Area | Where |
|---|---|
| Grid, cells, filters | `src/grid/` (FrameGrid, cells.ts, FilterBuilder) |
| Register pages, row detail, intake | `src/registers/` |
| App shell, routes, fields admin | `src/app/` |
| Corporate data UI | `src/corporate/` |
| Typed API client (generated envelope) | `src/api/client.ts` |
| REST surface (generic routers only) | `functions/api/routers/` (blueprints, rows, views, corporate_data, docs, health) |
| Domain logic | `functions/lib/` (blueprint, rows, views, permissions, grammar, corporate) |
| Event consumers | `functions/consumers/` |
| Product spec (normative) | `specs/frame-prds/*.md` |
| Architectural invariants | `tools/fitness/` |

Statuses — use exactly these five:

- **superior** — Frame's implementation or design beats theirs (cite why)
- **partial** — exists in code but narrower than theirs
- **absent** — no code, no PRD coverage
- **planned (PRD-only)** — specified in `specs/frame-prds/`, not yet built.
  Cite the PRD. (Verified example: Smartsheet automations → zero grep hits in
  `src/`, no router in `functions/api/routers/`, but
  `specs/frame-prds/04-prd-automation-and-workflow.md` covers it.)
- **blocked by design** — Frame's invariants forbid the competitor's
  *mechanism* (e.g. client-side row listeners, per-entity generated routers).
  Cite the CLAUDE.md break and the `tools/fitness/` test. The *user outcome*
  may still be achievable another way — say how, or route it to phase 4.

Every row cites a real path (`file:line` where useful). Grep before you
conclude "absent" — feature names differ; search synonyms (e.g. automation,
workflow, trigger, rule).

**Deliverable `03-gap-matrix.md`:** their feature ↔ Frame module/PRD ↔
status ↔ evidence.

## Phase 4 — Ideation: ranked opportunities

Turn the matrix into an **Opportunity Solution Tree** (structure in
templates.md): desired outcome → opportunities (from the matrix + review
pain points, i.e. evidence, not imagination) → 2+ solutions each → cheapest
experiment each.

Rank opportunities by **leverage**: impact on Frame's wedge (governed
metadata-defined work platform) ÷ effort, weighted by what the matrix says is
already partial or planned. Each opportunity must name the concrete module(s)
to extend or refactor — "extend `functions/lib/grammar/` to cover X",
not "add automations".

Guardrails:

- **No feature-parity traps.** "They have X so we need X" is copying, not
  strategy. Tie every opportunity to a user job Frame's governance/metadata
  wedge serves *better*, or drop it.
- **Never propose the four forbidden patterns** from CLAUDE.md (per-Blueprint
  routers, hand-maintained type mirrors, client-side access decisions or row
  listeners, wire-format case transforms). If a competitor wins *because* of
  one of these mechanisms, the opportunity is the alternative mechanism that
  preserves the invariant.
- Include at least one opportunity that **removes or simplifies** rather than
  adds, and one "what would make their differentiator irrelevant?" play.

**Deliverable `04-opportunities.md`,** ending with a 5-line executive
summary: top 3 opportunities, one line each, with the named module and the
first experiment.

## Gotchas

- **Pricing pages lie by omission.** Monthly-billed vs annual prices, and
  "contact us" tiers hide the real enterprise comparison. Note billing basis
  in the profile; never compare a fetched monthly price to a remembered
  annual one.
- **Changelogs paginate.** One WebFetch gets the latest page only; that's
  usually enough for trajectory, but say so in the sources list rather than
  implying full coverage.
- **`src/` greps returning nothing is normal.** Frame's build surface is
  deliberately small right now; the PRDs are the surface. A matrix that's
  mostly "planned (PRD-only)" is a correct result, not a failed analysis.
- **Review sites block direct fetches sometimes.** If g2.com WebFetch fails,
  WebSearch for the review content instead — result snippets are citable.
