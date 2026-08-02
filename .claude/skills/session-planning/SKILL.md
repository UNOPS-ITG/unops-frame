---
name: session-planning
description: Plan a Frame build session — one goal sentence, a P0/stretch scope drawn from the roadmap and backlogs, environment preflight, risks, and a definition of done anchored to the verify suites. Use at the start of a work session, when asked "what should we build next", when sizing how much fits before a deadline, or when handling carryover from a previous session.
argument-hint: "[session focus or 'next']"
---

# Session Planning (Frame)

Adapted from `sprint-planning` in
[anthropics/knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins)
(product-management plugin). Upstream plans a team sprint with capacity
tables and story points; Frame is built in focused sessions by one operator
plus this agent, so the unit shrinks — but the discipline that survives is
identical: **one goal sentence, a P0 set you would defend, stretch items you
know you'll cut, and honest carryover.**

## Ground rules

1. **One sentence of goal.** If the session's success can't be stated in one
   sentence, the session is unfocused — split it. ("The corporate picker
   works end-to-end against the emulator" is a goal; "work on corporate
   data" is weather.)
2. **Plan to ~70%.** Sessions get interrupted by discovered defects — this
   codebase's history says the discovered-bug tax is real (the deltas 500,
   the unloaded fonts, the 2.1 MB catalogue). Leave room; finding those IS
   the work, not a deviation from it.
3. **Carryover is examined, not re-committed.** If something didn't finish
   last session, name why (underestimated / blocked / deprioritized) before
   it earns a place in this one.
4. **Scope comes from the artifacts**, not from memory: `specs/roadmap.md`
   (Now column), `specs/ux-refresh.md` open items, the PRD phase tags, and
   `gcp-provisioning.md` for what *cannot* be scoped locally.
5. **New surfaces are staged frontend-first** (owner directive,
   2026-08-02): frontend built against hard-coded JSON fixtures shaped
   like the intended API contract → an explicit **vision verification**
   checkpoint where the owner confirms it feels right → only then the
   engine/backend, swapping fixtures for API shapes. Plan the checkpoint
   as a real session boundary: a P0's done-when may legitimately be
   "owner has seen it and confirmed the feel", and backend items for that
   surface do not enter a plan before the checkpoint has passed. Fixtures
   are commitworthy artifacts (they *are* the draft API contract), not
   throwaway scaffolding.

## Workflow

### 1. Preflight (2 minutes, prevents the classic hour-loss)
- Ports: `npm run ports`; check who actually holds them
  (`netstat`) — this machine accumulates zombie sockets, and the backend
  often runs on `FRAME_PORT_BACKEND` overrides. Record the ports the
  session will use.
- Emulator up? Seed fresh? (`node scripts/seed-dev-register.mjs` also clears
  e2e litter.)
- `git status` clean, on master, pushed.
- Baseline: is the full battery green *before* starting? If not, the first
  P0 writes itself.

### 2. Scope
Build the plan:

```
## Session plan — <date>
Goal: <one sentence>
Baseline: suites green? ports? seed?

| Pri | Item | Source | Done-when |
|-----|------|--------|-----------|
| P0  | ...  | roadmap/backlog/PRD id | <specific, checkable> |
| P0  | ...  |        |            |
| S   | (stretch) ... |  | cut first when the tax hits |

Carryover examined: <item — why it slipped — in/out this session>
Risks: <GCP blocker touching scope? port conflicts? migration touching
        normative PRD text (needs write-prd)? canvas work (needs perf run)?>
```

Every "done-when" is checkable, never "improve X". If an item's done-when
is a feeling, it is not scoped yet.

### 3. Definition of done (Frame's, fixed)
- `npm run verify` green (ports + lint + typecheck + fitness + unit).
- Browser suites green if the session touched UI
  (`npx playwright test`), perf suite if it touched the canvas.
- Backend pytest green if it touched `functions/`.
- Committed in reviewable slices with honest messages; pushed.
- Documents that claim status (README, roadmap, ux-refresh status,
  gcp-provisioning) updated **in the same commits** as the changes that
  altered the status.
- Discovered defects either fixed or landed as backlog/estate-findings
  entries — never left as chat-only knowledge.

### 4. Mid-session rule
When the discovered-bug tax exceeds the 30% buffer: cut stretch first, then
renegotiate P0 *explicitly* (say it, don't slide). A session that ships one
P0 with the suite green beats one that half-ships three.

## Gotchas
- Don't plan around an ultracode/token budget — plan around coherence: one
  subsystem's worth of context per session beats three shallow touches.
- The "quick UI tweak" that touches `brand-tokens.css` is never quick —
  three themes × fitness gates. Scope it as real work.
- If the session's goal needs anything from `gcp-provisioning.md`, the goal
  is wrong — rescope to the local-emulator boundary and note the seam.
