# Opportunities — Frappe Framework analysis

> Analysis date: 2026-08-02 · Analyst: Claude session for tushard@unops.org
> Sources fetched this session: see `01-profile.md` header (frappe@43666ea; discuss.frappe.io threads via search snippets).
> Shelf life: pricing/changelog claims stale after ~1 quarter.

Frappe is the metadata-engine benchmark leg of the three-competitor run
(`specs/discovery/smartsheet-frappe-monday/00-scope.md`). The question this file
answers: where does the real DocType implementation leave open ground that
Frame's Blueprint engine (which is modeled on it) should claim — and what did
the reference implementation get right that Frame has not yet specified?

## Opportunity Solution Tree

Desired outcome: Frame's "governed metadata platform" wedge demonstrably *beats*
the reference implementation it borrows from — measured by (a) catalog
Blueprints adopted without forking and (b) permission questions answerable
from one trace.

```
Desired outcome
├── O1 (leverage: high) Permission explainability from the single evaluator
│     traced to: matrix rows "Permission debug trace", "ABAC via dual hooks";
│     pain: discuss.frappe.io/t/109103 (fail-open leak), t/159712 (v16 regression)
│   ├── S1a: extend functions/lib/permissions/evaluate.py to emit a structured
│   │     decision trace (rule fired, condition value, ceiling applied) on demand —
│   │     the CompiledRule.specificity machinery already picks "which deny to report",
│   │     so the trace is largely computed and then thrown away today
│   │   └── Experiment: flag-gated trace return from evaluate_row + unit test
│   │         asserting every Decision can name its rule; ~1 day in functions/lib/permissions/
│   ├── S1b: steward-facing simulation — "evaluate this Blueprint as user X" endpoint
│   │     on the generic blueprints router (functions/api/routers/blueprints.py),
│   │     rendered in the fields admin (src/app/)
│   │   └── Experiment: read-only endpoint returning Decision + trace for a synthetic
│   │         row; demo to a steward persona (Ingrid) before building UI
│   └── Requirement home: PRD 05 (new PM-* requirement: every deny explainable;
│         complements PM-5 viewer-side transparency with steward-side tracing)
├── O2 (leverage: high) Adopt-with-overlay: the Property Setter lesson, governed
│     traced to: matrix row "Customization overlay" (status: absent) — the one
│     conceptual gap; Frappe proves shared metadata cores are only adopted when
│     sites can diff without forking (frappe/custom/*)
│   ├── S2a: a team-tier overlay document (extra fields, relabels, defaults,
│   │     view defaults — never permission weakening, never type changes) compiled
│   │     against the organizational base by functions/lib/blueprint/compile.py;
│   │     overlay legality validated at save like Frappe's fieldtype-change guards
│   │   └── Experiment: PRD 01 amendment (BP-* "adoption overlays") + a compile.py
│   │         spike merging base + overlay into one CompiledBlueprint; fitness test
│   │         asserting overlays cannot touch permission rules
│   ├── S2b: cheaper variant — no new document type: allow team-tier Blueprints to
│   │     declare `extends: <catalog id>` with additive-only fields, reusing the
│   │     existing tier machinery (Tier enum, functions/lib/blueprint/model.py)
│   │   └── Experiment: model.py schema sketch + steward review flow on promotion
│   │         (does the AI-assisted review diff overlay vs base cleanly?)
│   └── Requirement home: PRD 01 (BP-15..19 neighborhood — catalog and promotion)
├── O3 (leverage: medium) Workflow governance parity where Frappe is verifiably good
│     traced to: matrix row "Workflow engine" (partial); frappe/model/workflow.py
│   ├── S3a: transition conditions as shared-grammar ASTs (grammar already exists:
│   │     functions/lib/grammar/) instead of Frappe's safe_eval Python strings —
│   │     same conditions become analyzable by permissions, automations, and the
│   │     steward review; plus adopt the two governance details Frappe verified:
│   │     declarative no-self-approval per transition (workflow.py:301-302) and
│   │     bulk-action caps with per-doc savepoint semantics
│   │   └── Experiment: extend WorkflowTransition in functions/lib/blueprint/model.py
│   │         with condition: Expr + allow_self_approval: bool; compile-time
│   │         validation via lib/grammar/analyse.py; no engine needed yet
│   └── S3b: audit attribution parity — record acting-identity vs effective-identity
│         (Frappe's Version.set_impersonator) in functions/lib/rows/audit.py entries,
│         ahead of service identities (Workflow Studio, Playbook) acting through the API
│       └── Experiment: add actor/on_behalf_of fields to the audit entry model +
│             one test; PRD 05 audit requirement amendment
│   └── Requirement home: PRD 04 (AU-*) for S3a; PRD 05 (PM-*) for S3b
├── O4 (leverage: medium) Make "framework for developers" irrelevant: typed,
│     discoverable API surface without writing code
│     traced to: matrix row "Generic REST API" (partial) — Frame already publishes
│     per-Blueprint-version OpenAPI (functions/api/routers/docs.py), which Frappe
│     does not; Frappe counters with bulk ops + discovery endpoints
│   ├── S4a: close the bulk gap on the generic rows router — bulk update/delete with
│   │     async-over-threshold + job-id semantics (the frappe/api/v2.py:31-39 pattern),
│   │     implemented once in functions/api/routers/rows.py + functions/lib/rows/writer.py
│   │     (single row writer stays the only writer, BP-4)
│   │   └── Experiment: 202+job contract sketch in PRD; measure import path reuse in
│   │         lib/rows/importer.py before writing any new code
│   └── S4b: point the same generated OpenAPI at the MCP surface (PRD 08) so agents
│         get typed Blueprints where Frappe's agents get untyped doc dicts —
│         with PM-5 annotations in every tool response (the differentiator the
│         vision claims; frappe has no equivalent)
│       └── Experiment: generate one MCP tool schema from an existing
│             blueprint_openapi payload; no server work
│   └── Requirement home: PRD 09 (API/webhooks) for S4a; PRD 08 for S4b
└── O5 (leverage: medium, remove/simplify play) Refuse the three Frappe mechanisms
      whose costs the evidence now documents — and say so in the PRDs
      traced to: matrix rows "DocShare", "Server Script", "permlevel bands";
      pain: fail-open User Permission incident (discuss.frappe.io/t/109103)
    ├── S5a: record the verified evidence in PRD 05 as rationale notes on PM-2a/PM-4
    │     and N5/N8 (this analysis provides the citations: share.py OR-path,
    │     safe_exec site-config gating, permlevel linear bands) so future
    │     "just add per-row sharing" debates are settled by reference, not memory
    │   └── Experiment: PRD amendment only; zero code
    └── S5b: add a fitness check that the permission rule vocabulary contains no
          per-row grant primitive and no integer sensitivity band — making N8
          checkable rather than remembered (tools/fitness/architecture.test.ts
          pattern: log "not yet enforced" until the vocabulary lands)
        └── Experiment: one fitness test against functions/lib/permissions/model.py
```

## Ranked list

| # | Opportunity | Named module(s) | Leverage | Why now |
|---|---|---|---|---|
| 1 | Permission explainability (steward-side trace + simulate-as-user) | `functions/lib/permissions/evaluate.py`, `functions/api/routers/blueprints.py`, PRD 05 PM-* | High | The single-evaluator invariant makes a complete trace *possible only for Frame*; Frappe's dual-path ABAC cannot ever explain a list trim. Evaluator is built and young — cheapest moment to add. Directly serves Ingrid and the ABAC-transparency wedge |
| 2 | Adopt-with-overlay for catalog Blueprints | `functions/lib/blueprint/compile.py`, `functions/lib/blueprint/model.py`, PRD 01 BP-15..19 | High | The one *conceptual* absence the benchmark exposed; without it the promotion ladder risks forks and catalog rejection — the exact sprawl Frame exists to prevent. Spec-first, code later |
| 3 | Workflow conditions on the shared grammar + no-self-approval + audit impersonation | `functions/lib/blueprint/model.py`, `functions/lib/grammar/analyse.py`, `functions/lib/rows/audit.py`, PRD 04 AU-*, PRD 05 | Medium | Metadata model exists; adding grammar conditions now prevents ever shipping a safe_eval-shaped stopgap. Governance details are verified-cheap wins |
| 4 | Typed API completeness: bulk ops with job semantics; OpenAPI→MCP | `functions/api/routers/rows.py`, `functions/lib/rows/writer.py`, `functions/api/routers/docs.py`, PRD 09, PRD 08 | Medium | Frame already beats Frappe on typed OpenAPI; bulk semantics are the remaining verified gap for integrators and migration tooling |
| 5 | Refuse-and-record: no DocShare, no user scripting, no permlevels — with citations and a fitness check | PRD 05 amendments (PM-2a, PM-4, N5/N8 rationale), `tools/fitness/` | Medium | Zero build cost; converts this analysis into durable guardrails before the permission vocabulary grows |

Guardrail check: no per-Blueprint routers, no hand-maintained type mirrors, no
client-side access or row listeners, no wire-format case transforms proposed
anywhere above. O5 is the remove/simplify play; O1 and O4b are the
"make their differentiator irrelevant" plays (their permission debug trace and
their developer-first API story respectively). No feature-parity traps taken:
docstatus amend chains, multi-DB backends, per-document sharing and Server
Script were considered and deliberately *not* carried over (matrix rows give
the reasons).

## Executive summary

1. **Permission explainability** → `functions/lib/permissions/evaluate.py` + PRD 05 → first experiment: flag-gated decision trace from `evaluate_row`, then a simulate-as-user endpoint on the generic blueprints router.
2. **Adopt-with-overlay** (the Property Setter lesson, governed) → `functions/lib/blueprint/compile.py` + PRD 01 → first experiment: PRD amendment plus a compile-time base+overlay merge spike with a fitness test that overlays can never weaken permissions.
3. **Grammar-based workflow conditions + no-self-approval + impersonation audit** → `functions/lib/blueprint/model.py`, `functions/lib/rows/audit.py`, PRD 04/05 → first experiment: extend `WorkflowTransition` with a grammar `condition` and `allow_self_approval`, validated by `lib/grammar/analyse.py` at Blueprint save.

## Post-synthesis correction (2026-08-02, pipeline phase 4)

O2 ("adopt-with-overlay") overstated the gap: BP-19 already specifies the
governed overlay (see the correction in `03-gap-matrix.md`). O2's residual
value landed as **BP-27 (overlay convergence reporting)** in PRD 01; the
rest of O2 is build work against an existing spec, not a spec gap. O1 and
O3 landed as PM-14 (PRD 05) and AU-15 + PRD 04 open question 4
respectively.
