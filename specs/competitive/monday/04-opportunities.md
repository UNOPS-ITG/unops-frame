# Opportunities — Monday.com Enterprise analysis

> Analysis date: 2026-08-02 · Analyst: Claude session for tushard@unops.org
> Sources fetched this session: see 01-profile.md header (same set).
> Shelf life: pricing/changelog claims stale after ~1 quarter.

## Opportunity Solution Tree

Desired outcome: **governed Blueprints beat board sprawl** — teams adopt
Frame because the governance is the product, not the upsell; measured by the
vision §8 metrics (top-20 registers on org Blueprints, keyed corporate
columns, unforced adoption).

```
Desired outcome: governed Blueprints beat board sprawl
├── O1 (leverage: high) Recipe-grade automation packaging — Monday's D1 is
│   packaging, not engine; Frame's AU-* engine design is the same
│   trigger/condition/action-as-data shape, and the condition grammar is built
│   ├── S1a: build the AU-1/AU-3 engine with a code-first recipe gallery —
│   │   preconfigured trigger+condition+action records over the closed action
│   │   vocabulary, rendered as a Monday-style sentence builder; conditions
│   │   compile through the existing functions/lib/grammar/ AST
│   │   └── Experiment: paper-catalog 10 recipes against the three pilot
│   │       registers' real needs; pass = ≥80% expressible in the closed
│   │       vocabulary (AU-3) without scripting (N5)
│   └── S1b: NL-to-recipe authoring (PRD 08 native assist) — user describes
│       the rule, AI emits the AST + action record for review; leapfrogs
│       Monday's menu-driven builder because Frame has one grammar for all
│       └── Experiment: prompt-only prototype: 20 real rule descriptions from
│           pilot teams → hand-checked AST; pass = ≥15 correct without edits
├── O2 (leverage: high) The admin estate view Monday admins are begging for —
│   verified pain: admins can't see/administer unowned boards, duplication
│   forks permissions silently, managed templates are quota'd copies
│   ├── S2a: build the catalog + tier surface early (BP-15..BP-19): extend
│   │   functions/lib/blueprint/store.py with tier/provenance queries and a
│   │   steward estate view in src/app/ listing every Blueprint, tier, owner,
│   │   exposure (PM-13), and adoption — governance that sees everything by
│   │   construction, because Blueprints are registered, not discovered
│   │   └── Experiment: read-only estate page over existing blueprint store
│   │       docs; show it to the pilot stewards next to their current
│   │       Smartsheet/Monday sprawl; measure "what would you catch with this"
│   └── S2b: GOVERNANCE audit class surfaced as a feed (functions/lib/rows/
│       audit.py already defines it): every rule change, promotion, masking
│       toggle in one queryable stream — the thing Monday's audit API can't do
│       └── Experiment: wire GOVERNANCE events from blueprint save/compile
│           into the existing audit stream; demo a one-week diff to a steward
├── O3 (leverage: medium-high) Audit that covers data, not just admin events —
│   Monday's Enterprise audit catalogue is logins/exports/permission changes;
│   Frame's PM-7 CHANGE class carries field-level deltas trimmed by the same
│   permission Decision
│   ├── S3a: finish the CHANGE pipeline: emit from functions/lib/rows/writer.py
│   │   through audit.py, render an activity drawer in
│   │   src/registers/RowDetail.tsx with "(value withheld)" stubs per PM-10
│   │   └── Experiment: activity drawer on one pilot register; verify a
│   │       restricted field's delta renders withheld for a non-cleared viewer
│   └── S3b: ACCESS-class export/SIEM surface (PM-7): a generic audit query
│       endpoint in functions/api/routers/ (generic — not per-Blueprint),
│       matching what Monday gates to Enterprise
│       └── Experiment: estate security team reviews a sample export; pass =
│           it answers their standard access-review questions unaided
├── O4 (leverage: medium) Make their metering irrelevant — Monday monetizes
│   250/25K/250K action quotas, API call tiers, AI credits, and template
│   quotas; Frame has no seats and no meters
│   ├── S4a: publish "no metering" as an explicit product principle in PRD 04
│   │   (AU-*) and PRD 12, replacing quotas with engineering budgets: storm
│   │   control (PRD 12), automation loop guards (AU-*), and per-workspace
│   │   cost attribution (the PRD 14 pattern) — governance instead of tolls
│   │   └── Experiment: none needed to state it; the test is the storm-control
│   │       design review in PRD 12
│   └── S4b: add the one thing their metering does well — visibility: an AI/
│       automation usage view per workspace (their May 2026 AI Admin Usage
│       dashboard), as a PRD 08 amendment; attribution, not billing
│       └── Experiment: log-derived usage table for pilot workspaces before
│           committing UI
└── O5 (leverage: medium, remove/simplify play) Refuse the marketplace —
    Monday needs 850+ apps because a semantically empty board can't finish
    the job (87% of their enterprise accounts install apps to close gaps);
    Frame's composition answer is already governed Blueprints + views
    ├── S5a: re-scope PRD 10 App Composer to composition-only (views, forms,
    │   dashboards, navigation over existing Blueprints) and record the
    │   non-goal: no third-party app runtime, no app review process, no
    │   widget SDK — the metadata surface is the extension point
    │   └── Experiment: rebuild one "would-be marketplace app" need from a
    │       pilot team (e.g. an approvals mini-app) as pure composition; if it
    │       needs code, that's a field-type or action-vocabulary request
    │       (code-first config), not an app
    └── S5b: where genuine extension pressure exists, route it to the estate
        pattern: MCP tools (PRD 08) and the published event contract (AU-8)
        are Frame's "apps framework" — external logic subscribes and calls
        back through the API under its own identity (the fitness-enforced
        consumer rule)
        └── Experiment: implement one integration consumer end-to-end through
            functions/consumers/ to prove the extension story without a runtime
```

**"Make their differentiator irrelevant" plays:** O4 dissolves D1's
monetization edge (metering has no power where there are no seats), and the
corporate-data module — already built in `functions/lib/corporate/` and
`src/corporate/` (PRD 14) — dissolves D3/D4's data story outright: no SaaS
outside our tenancy can resolve a picker inside our warehouse as our staff
member. Every pilot demo should end on a corporate-bound column for exactly
this reason.

## Ranked list

| # | Opportunity | Named module(s) / PRD | Leverage | Why now |
|---|---|---|---|---|
| 1 | Recipe-grade automation packaging on the AU engine | new `functions/lib/automations/` per PRD 04 (AU-1, AU-3, AU-3a); conditions via existing `functions/lib/grammar/`; NL authoring per PRD 08 | High | Biggest verified capability gap vs Monday's strongest ground; grammar + writer + event outbox (`functions/lib/rows/outbox.py`) already exist, so the engine is mostly assembly |
| 2 | Steward estate view: catalog, tiers, exposure register | `functions/lib/blueprint/store.py` + `src/app/`; BP-15..BP-19, PM-13, PM-7 | High | Monday's admins verifiably cannot get this; it is Frame's wedge made visible, and it de-risks the promotion ladder (vision risk #2) |
| 3 | Data-grade audit surface (CHANGE drawer + ACCESS export) | `functions/lib/rows/audit.py`, `functions/lib/rows/writer.py`, `src/registers/RowDetail.tsx`; PM-7, PM-10 | Medium-high | Half-built already; beats Monday's Enterprise-gated, admin-events-only audit API on both depth and honesty |
| 4 | No-metering principle + usage visibility | PRD 04 (AU-*), PRD 12 storm control, PRD 08 amendment for AI/automation usage attribution | Medium | Free positioning win; the usage-visibility gap (their AI Admin Usage dashboard) is the one real hole worth a PRD amendment |
| 5 | Refuse the marketplace; App Composer stays composition-only | PRD 10 re-scope; extension via PRD 08 MCP + AU-8 event contract; `functions/consumers/` | Medium | Removes an entire product surface from the backlog and converts D2 from a gap into a non-goal with a stated alternative |

Guardrail check: no per-Blueprint routers (O3b/O5 explicitly generic), no
client-side access decisions, no type mirrors, no wire case transforms; O5 is
the remove/simplify play; O4 and corporate data are the make-irrelevant
plays; N1, N3, N5, N7, N11, N12 all respected (no workdocs, no embedded BPMN
builder, no scripting tier, no guest editing, no resource management, no
marketplace).

## Executive summary

1. **Automation packaging (O1)** → build AU-1/AU-3 engine with a code-first recipe gallery over `functions/lib/grammar/`; first experiment: 10 recipes vs the pilot registers' real needs, ≥80% expressible in the closed vocabulary.
2. **Steward estate view (O2)** → extend `functions/lib/blueprint/store.py` + `src/app/` per BP-15..19/PM-13; first experiment: read-only estate page shown to pilot stewards against their current sprawl.
3. **Data-grade audit (O3)** → finish PM-7 CHANGE pipeline through `functions/lib/rows/audit.py` into a RowDetail activity drawer; first experiment: verify withheld-value rendering on one pilot register.
Monday's governance is an Enterprise-tier overlay on semantically empty boards — Frame's is the data model; the demo that no Monday deployment can answer is the corporate-bound column already built in `functions/lib/corporate/` (PRD 14).
