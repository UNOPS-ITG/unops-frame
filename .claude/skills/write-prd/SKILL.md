---
name: write-prd
description: Write or amend a Frame PRD in the house style — numbered normative requirements with phase tags, index integration, cross-reference discipline, and fitness-checkable acceptance. Use when turning a feature idea or problem statement into a spec, adding requirements to an existing PRD, scoping with goals and non-goals, or when asked to "spec" or "write a PRD for" anything.
argument-hint: "<feature, problem statement, or PRD to amend>"
---

# Write PRD (Frame house style)

Adapted from `write-spec` in
[anthropics/knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins)
(product-management plugin). The generic advice there (tight P0s, honest
non-goals, testable acceptance) survives; the format does not — Frame has a
normative house style, and a PRD that ignores it is unreviewable against the
other fifteen documents.

## Ground rules

1. **The PRDs are normative and live in `specs/frame-prds/`.** Read
   `product-vision-frame.md` and `00-prd-index.md` before writing anything.
   The index carries the shared definitions, personas, cross-cutting NFRs and
   the code-first configuration doctrine — a new PRD must not restate them and
   must not contradict them.
2. **Amend before you create.** Most "new feature" asks belong inside an
   existing PRD as new numbered requirements. A new PRD file is justified only
   for a genuinely new subsystem (the bar PRD 14 cleared). When amending,
   continue the document's numbering; never renumber existing requirements —
   they are cited from other PRDs, code comments and commit messages.
3. **Requirements are the unit.** Format, exactly:
   `**XX-N (P1).** Requirement prose.` — bold id with phase tag, then
   normative text where "must" means must. One requirement = one enforceable
   claim plus its rationale. Frame PRDs argue *why* inline (see CD-2's "a slow
   gate is not bypassed politely, it is bypassed"); a bare imperative without
   its reason is not house style.
4. **Prefix registry** (do not collide): BP (01), GR (02), FM (03), AU (04),
   PM (05), RP (06), DG (07), AI (08), IN (09), AC (10), NT (12), SR (13),
   CD (14). A new PRD claims a new two-letter prefix and a row in the index's
   document map.
5. **Phases are the vision's, not invented.** P1/P2/P3 map to vision §9. A
   requirement's phase is a scoping decision — record contentious ones as an
   open question rather than silently tagging.

## Workflow

### 1. Scope the ask
Classify: new requirement(s) in an existing PRD / new PRD / amendment to an
existing requirement (which means a *new* requirement that supersedes,
citing the old id — never silent edits to normative text others may have
built against; check `git log -S "XX-N"` and grep `src/ functions/ tools/`
for citations first).

### 2. Gather context (from the repo before the user)
- The PRD(s) covering adjacent territory, fully.
- Vision sections it touches; the numbered non-goals **N1–N12** — if the ask
  collides with one, stop and say so rather than spec around it.
- The four deliberate breaks in `CLAUDE.md` and `tools/fitness/` — a
  requirement whose only implementation would violate one is a defective
  requirement.
- What already exists in code (grep `src/`, `functions/`): "specified and
  partially built" changes what the PRD should say.

Ask the user only what the repo cannot answer: the user problem and who has
it (map to the index personas — Maya/Daniel/Ingrid/Kofi/Amara), hard
constraints, and what decision the spec unblocks.

### 3. Draft
Structure for a new PRD (mirror PRD 14, the newest exemplar):

```
# PRD NN: <Name>
Version 0.1, <month year>. Part of the Frame PRD set; see 00-prd-index.md.
## Purpose        — 1-2 paragraphs: the job, the wedge, why Frame
## Scope          — in/out in prose; out-of-scope cites vision N-numbers
## <capability sections>   — the numbered requirements live here
## Open questions — genuinely open, each tagged with who answers
```

Requirement discipline:
- **Goals as outcomes** live in Purpose; requirements are enforceable claims.
- **Non-goals** cite their reason and, where they echo the vision, the
  N-number that owns them.
- **Acceptance is checkable.** Prefer requirements whose violation a machine
  can catch; where an invariant is load-bearing, name the fitness test that
  should exist ("the enumeration is the CI test" — CD-8 pattern). A
  requirement nobody could write a test or a review checklist for is a wish.
- **Cross-reference by id**, and only ids that exist. Every new mechanism
  should say which existing mechanism family it joins (CD-13's "one mechanism
  family, not two" pattern) — two mechanisms for one job is how estates rot.
- **Tight P1.** If cutting it still solves the core problem, it is not P1.

### 4. Integrate
- Update `00-prd-index.md`: document map row (new PRD), shared definitions
  (new nouns used by 2+ PRDs), and nothing else.
- Add dependency mentions in the PRDs that consume the new requirements.
- If the feature has GCP prerequisites, add them to
  `specs/frame-prds/gcp-provisioning.md` with what they block.

### 5. Verify (do not skip)
- Every cross-referenced id resolves: grep each `[A-Z]{2}-\d+` you wrote
  against the PRD set.
- No new requirement contradicts a fitness test or a deliberate break.
- Phase tags consistent with vision §9.
- Read it back as Ingrid (time-poor steward): headers + bold alone must
  carry the gist.

## Gotchas
- The index's "Conventions" section is one paragraph and easy to miss; it is
  the format contract.
- "Open questions" that the repo can answer are padding — answer them.
- A PRD amendment that changes behaviour already built needs the code, tests
  and this spec updated in the same change, or the suite goes green while
  protecting the wrong claim.
