---
name: synthesize-research
description: Synthesize user research — pilot feedback, interview notes, support items, session directives — into ranked findings that each land somewhere concrete in Frame (a PRD amendment, a backlog item, an estate finding, or an explicit park). Use when there is a pile of feedback to make sense of, after a pilot or demo round, or when turning raw quotes into roadmap input.
argument-hint: "<research topic, or where the raw material lives>"
---

# Synthesize Research (Frame)

Adapted from `synthesize-research` in
[anthropics/knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins)
(product-management plugin). The upstream methodology (thematic analysis,
frequency × impact, triangulation) survives intact; the Frame adaptation is
the landing rule: **a finding that does not land somewhere in this repo is a
finding that will be lost.**

## Ground rules

1. **Quotes are verbatim and attributed** (role, not name, if sensitivity
   requires). A paraphrase is analysis, not evidence, and the two are never
   mixed in one cell.
2. **Behaviour beats opinion.** What someone *did* (kept exporting to Sheets,
   typed the project name as free text) outranks what they *said*. Frame's
   vision is explicit that the honest adoption metric is behavioural (§8:
   "staff choose it without being told to").
3. **Map every finding to a persona** from `00-prd-index.md`
   (Maya/Daniel/Ingrid/Kofi/Amara). A finding that fits no persona is either
   a new persona (worth surfacing) or out of scope (say which).
4. **The landing rule.** Every kept finding ends in exactly one of:
   - **PRD amendment** — cite the PRD and requirement id it changes or adds
     (then offer to run `/write-prd`);
   - **Backlog item** — appended to the relevant backlog
     (`specs/ux-refresh.md` for UX, or the roadmap's Later column);
   - **Estate finding** — a defect in a sibling product goes to
     `specs/frame-prds/estate-findings.md` in its per-app section;
   - **Parked** — with the reason (out of scope per vision N1–N12, too few
     signals, contradicted by stronger evidence). Parked is a decision, not
     a euphemism for dropped.

## Workflow

### 1. Gather
Accept pasted notes, files, or pointers to repo material. Ask only what the
material cannot answer: how many participants/sources, what question this
research was meant to answer, and what decision it informs. Distinguish
source types — an interview, a support complaint, and a stakeholder opinion
carry different weight and different bias.

### 2. Extract per source
Observations, verbatim quotes, behaviours (vs statements), pain points,
positive signals, and the context (persona, tier of Blueprint, whether they
touched governed features — withheld rows, corporate refs — or only the
plain grid).

### 3. Theme and rank
Affinity-group observations into themes. For each theme: frequency (how many
independent sources), impact (blocks the job / degrades it / annoys), and
confidence (triangulated across source types?). Priority matrix:

| | High impact | Low impact |
|---|---|---|
| **High frequency** | Top findings | Quality-of-life queue |
| **Low frequency** | Segment-specific — name the persona | Note and park |

Contradictions and surprises get their own section — a pilot user who
*likes* something the team assumed was a problem is the most valuable row in
the document.

### 4. Deliverable
Write `specs/research/<date>-<topic-slug>.md`:

```
# Research synthesis: <topic>
Date · sources (type + count) · question · decision this informs
## Top findings          — ranked; each: theme, evidence (quotes+counts),
                            persona, impact, and its LANDING (rule above)
## Segment-specific findings
## Contradictions & surprises
## What this does NOT support   — claims someone might want this research
                                   to justify, that it does not
## Landings ledger       — one line per finding → where it went
```

Then actually do the landings: append backlog items, add estate findings,
and offer to draft the PRD amendments.

## Gotchas
- **Small-n honesty.** Three interviews support "we heard", never "users
  want". State n everywhere; the scorecard discipline from the vision's
  measurable-metrics stance applies to research too.
- **The loudest source is usually the least representative** (the person who
  escalated). Weight by persona coverage, not volume.
- **Frame-specific bias trap:** feedback gathered inside the demo register
  is feedback about seed data ergonomics as much as about the product. Note
  which findings could be artifacts of the demo dataset.
