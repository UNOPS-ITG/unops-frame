---
name: stakeholder-update
description: Generate a stakeholder update on Frame from repo evidence — git history, suite results, roadmap and blocker status — tailored to audience (owner/engineering, steward/leadership, estate teams). Use for a weekly or milestone status, announcing something shipped, escalating a blocker, or translating the same progress for different readers.
argument-hint: "<audience and period, e.g. 'leadership, this week'>"
---

# Stakeholder Update (Frame)

Adapted from `stakeholder-update` in
[anthropics/knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins)
(product-management plugin). Upstream pulls from trackers and chat; Frame's
tracker **is the repo**, so the update is assembled from evidence the way
everything else here is: git history, the suites, and the status documents.
The voice rule survives from upstream unchanged: outcomes, not activity.

## Ground rules

1. **Evidence-assembled.** Before writing: `git log --oneline --since=<period>`
   (plus `--stat` for shape), the current suite counts (run them or cite a
   run from this session), `specs/roadmap.md`, `specs/frame-prds/gcp-provisioning.md`,
   and `specs/frame-prds/estate-findings.md` for anything new that concerns
   other teams. Numbers in the update are real numbers.
2. **Outcomes, not activity.** "The register now refuses a stale edit and
   shows what won" — not "worked on conflict handling". Every claimed
   outcome should be demonstrable at a URL or in a test.
3. **Blockers carry an ask.** A blocker without a named owner and a concrete
   ask ("provisioning item 5: a service account in exactly the all-staff
   group — needs ITG") is an excuse, not an escalation.
4. **Honesty beats polish.** If something regressed, slipped, or was cut, it
   is in the update with its reason. Frame's product thesis is visible
   governance; its reporting should not be the exception.

## Audiences (pick one; offer the others as variants)

- **Owner / engineering** — full depth: defects found *and their causes*
  (this repo's best material — the unloaded-fonts class, the keyword-only
  `order_by`), invariants touched, test deltas, file-level pointers.
- **Steward / leadership** — outcome-framed, demo-linked, one screenshot
  beats three paragraphs; governance wins stated in product terms ("two
  people, one URL, legitimately different rows"); blockers as decisions
  needed, not technology.
- **Estate teams** — only what concerns them: new `estate-findings.md`
  entries (each with severity and suggested owner), shared-rubric changes
  (e.g. "the estate's tokens name Inter; nothing loads it — portable fix"),
  and contract-shaped things (event schemas, connector patterns) they may
  want to reuse.

## Structure (all audiences, depth varies)

```
# Frame update — <period> (<audience>)
**TL;DR** — 2–3 sentences: the headline outcome, the headline risk.

## Shipped        — outcome bullets; each demonstrable (URL, test, screenshot)
## In progress    — with expected next checkpoint, not dates invented for comfort
## Blockers & asks — blocker ↔ owner ↔ concrete ask ↔ what it unlocks
## Numbers        — suite counts, perf/payload numbers measured this session,
                    with movement vs last update where a last update exists
## For your attention (estate/leadership variants) — findings, decisions needed
```

Deliverable: `specs/updates/<date>-<audience>.md` when the user wants it
kept, chat-only when they want it pasted elsewhere. Ask which — it changes
nothing else.

## Cadence patterns

- **Weekly**: assemble from `git log --since="1 week ago"`; compare suite
  counts to the previous update file if one exists.
- **Milestone/launch**: lead with the demo claim proven (for M1: the
  two-persona split at one URL, and how to reproduce it — `npm run demo:m1`);
  include the "what this does not do yet" section — it pre-empts the
  question every steward asks.
- **Escalation (ad-hoc)**: one page max; the blocker, the cost of waiting
  (tie to what it blocks in `gcp-provisioning.md`), the specific ask, the
  fallback if refused.

## Gotchas
- **Commit messages here are unusually rich** — mine them, but translate:
  a leadership update quoting "keyword-only `order_by`" has failed its
  audience.
- **Don't let the defect list read as instability** to non-engineers: frame
  found-defects as the verification system working ("caught before any user
  saw it"), which is also simply true.
- Screenshots: capture fresh (`.artifacts/` harnesses exist) — a stale
  screenshot claiming current state is a small lie with a long life.
