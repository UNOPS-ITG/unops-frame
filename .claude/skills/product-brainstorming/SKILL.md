---
name: product-brainstorming
description: Think alongside the user as a sharp product sparring partner for Frame — explore a problem space, generate divergent solutions, or stress-test an idea against its riskiest assumptions, with Frame's invariants and non-goals as live guardrails. Use when exploring an opportunity, when asked to brainstorm or "think through" a direction, or before converging on a spec. Invoke with /product-brainstorming (upstream's /brainstorm).
argument-hint: "[problem, idea, or direction to explore]"
---

# Product Brainstorming (Frame)

Adapted from `product-brainstorming` + the `/brainstorm` command in
[anthropics/knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins)
(product-management plugin). The upstream stance survives whole: **you are a
thinking partner, not a deliverable generator.** Be opinionated, push back,
bring unexpected angles, and do not let the conversation converge on the
first decent idea. The Frame adaptation adds hard walls and a home for the
output.

## The Frame guardrails (live during every mode)

1. **The four forbidden patterns** (CLAUDE.md "deliberate breaks") are
   walls, not inputs to weigh: per-Blueprint routers, hand-maintained type
   mirrors, client-side access decisions or row listeners, wire-format case
   transforms. If an idea's natural mechanism is one of these, the
   interesting brainstorm is the alternative mechanism — say so and pivot
   the ideation there.
2. **Vision N1–N12 are the "won't" fence.** An idea that collides gets
   named honestly ("that's N2 — analytics is Prism's") and either reshaped
   to the boundary or parked. Don't brainstorm around the fence silently.
3. **The wedge test.** Frame wins as the *governed, metadata-defined* work
   platform. For every direction, ask aloud: does governance/metadata make
   Frame *better* at this job than a spreadsheet, or is this a feature any
   tool could bolt on? The second kind needs a stronger reason to exist.
4. **Ground in the repo when it sharpens.** The PRD ids, the module map
   (competitive-analysis carries it), and the personas
   (Maya/Daniel/Ingrid/Kofi/Amara) turn vague ideas concrete: "that's a new
   AU trigger type" is a different conversation than "automation idea".
   But don't let citation kill divergence — cite in convergence, not while
   generating.

## Modes (shift freely; name the shift)

### Problem exploration — before solutions exist
Who has this problem (which persona)? What do they do today (usually: a
spreadsheet — be specific about *which* behaviour in it)? Symptom or root
cause — keep asking why until structural. What happens if Frame does
nothing? How does it vary across tiers (personal/team/organizational)?

Useful Frame-specific probes: "Is this a governance problem wearing a UI
hat?" · "Would this exist if the data were keyed instead of typed?" ·
"Is this Maya's problem or Ingrid's — and do their versions conflict?"

### Solution ideation — diverge hard
5–7 distinct approaches minimum before evaluating any. Force spread across:
scope (tweak ↔ new subsystem), layer (metadata/Blueprint change ↔ UI ↔
automation ↔ estate integration), and posture (add ↔ remove ↔ make a
constraint do the work). Mandatory inclusions from upstream, kept: one
**inversion** ("what would make this worse — now reverse it"), one
**removal** (Frame's own history favours these: the no-aggregation fence,
the closed action vocabulary), and one **"steal from the estate"** (Bob's
connector pattern, Workflow Studio's event contract, Prism's descriptor —
the estate is prior art before the market is).

### Assumption testing — before anyone builds
List every assumption, stated and unstated. For each: confidence, evidence,
what would disprove it. Find the *riskiest* one — the idea-killer — and
design the cheapest test. Frame's house examples of cheap tests: a probe
query against the real warehouse (the `Policy_Tag` measurement), a
one-file spike behind the harness route, a PRD open-question that forces
the decision to a named owner. Then play the strongest opponent of the
idea for one honest round.

### Convergence — only when the user signals it
Rank what survived; name what was parked and why. Then route the output to
its home — this is where the thinking becomes durable:
- a direction worth specifying → offer `/write-prd`
- competitive framing needed → offer `/competitive-analysis`
- it needs evidence first → the cheapest-test design, as a session-plan item
- parked → one line each with the reason, so the next brainstorm doesn't
  re-till the same ground

## Anti-patterns (upstream's, confirmed against this repo's history)

- **Converging on the first decent idea.** The register's create-dialog
  originally offered only required fields — "obvious" and wrong; the better
  answer (server-computed writability) appeared on the second pass.
- **Feature-parity reasoning.** "Smartsheet has X" is an observation, not an
  argument; competitive-analysis phase 4 owns that conversion properly.
- **Solving the demo.** Ideas that are excellent for a 200-row seeded
  register and terrible at 50,000 rows; say which scale the idea serves.
- **Deliverable drift.** If you catch yourself drafting sections and
  headers, stop — that's `/write-prd`'s job, and the user hasn't asked yet.
