# The paper catalog: four pilot registers vs the closed vocabulary

Answers PRD 04 open question 4 (now its decisions log): can the AU-2
trigger and AU-3 action vocabularies express the pilot registers' real
intake/workflow/automation needs without scripting? Registers supplied by
the repo owner, 2026-08-02: contract management, asset management,
project management, fleet management. Zero code was written to produce
this file; that is the point.

Verdict key: **AU-1** = expressible as an automation record today ·
**AU-1\*** = expressible after this run's vocabulary refinements (AU-16
computed parameters, AU-17 sweep semantics) · **mech:X** = served by a
declared mechanism, not an automation (a point in the model's favour —
rollups, formulas and conditional properties are analyzable where
automations are merely auditable) · **WS** / **PB** = routes to Workflow
Studio / Playbook by design (the graduation ladder working, not a
vocabulary failure) · **spec** = surfaced a genuinely open spec question.

## 1 · Contract management

Shape: Blueprint `contract-tracker`; corporate reference to the contract
dimension (header read-only from the warehouse by definition); corporate
figures at contract grain — amount paid, amount committed (see the N10
guard below); added fields: performance rating, delivery status,
logistics; goods-conditional fields (item locations, warehouse) via
BP-3a; child collection: deliveries. States: Active → Under review →
Closed.

| # | Need | Expression | Verdict |
|---|---|---|---|
| C1 | New contract row → default state, assign manager | row created → set field, assign user | AU-1 |
| C2 | End date approaching (60/30d) → notify manager | date-field approaching → notify. End date is a carried attribute (PRD 14, P2) — phasing note, not vocabulary | AU-1 |
| C3 | Rating set to Poor → notify supervisor, open issue | row updated (rating) → cond → notify + create row (issue register) | AU-1 |
| C4 | Monthly performance check on active goods contracts | scheduled → cond `state = Active and type = "goods"` → notify (per-row, AU-17) | AU-1 |
| C5 | Parent shows last delivery date from child rows | rollup `latest(deliveries.date)` | mech:BP-10 |
| C6 | Paid ≥ 90% of committed → alert | scheduled → cond `amount_paid >= 0.9 * amount_committed` → notify. Grammar arithmetic ✓; corporate figures are P3, so the *need* phases with them | AU-1 |
| C7 | Goods contracts require warehouse/location fields | `required_when: type = "goods"` | mech:BP-3a |
| C8 | Closure gated to contract-manager role, approved, no self-approval | AU-10 transition + request approval + AU-15 default | AU-1 |
| C9 | Quarterly performance document per contract | scheduled → generate document | AU-1 |
| C10 | Issue unresolved 14 days → escalate | expressible today by stamping a date on state entry + date-field reached; native shape is the elapsed-in-state primitive — evidence appended to PRD 04 OQ3 | AU-1 (friction) |
| C11 | Upstream contract closed in warehouse → flag the row | staleness/quarantine handles display (PRD 14 D6); whether a carried-attribute refresh fires `row.updated` triggers is genuinely unspecified → new PRD 04 open question 4 | spec |
| C12 | Supplier performance letter on review completion | state changed → generate document + notify (email) | AU-1 |

## 2 · Asset management

Shape: Blueprint `asset-register`; supplier corporate reference; child
collections: assignment history, verification records. States: In
transit → Received → In storage → Issued → Under repair → Disposed.

| # | Need | Expression | Verdict |
|---|---|---|---|
| A1 | Goods receipt intake creates asset rows | form submitted → initial state (FM-7); bulk arrivals via import (IN-13) | AU-1 |
| A2 | Issue-to-user: request form → approval → issued | form submitted → request approval → change state + set custodian | AU-1 |
| A3 | Not verified in 12 months → verification task to custodian | date-field reached (`last_verified + 12mo`) → create row + notify (per-row, AU-17) | AU-1 |
| A4 | Custodian confirms condition remotely | AU-4a update request (P2), scoped mini-form | AU-1 |
| A5 | Condition = Damaged → repair flow | row updated (condition) → change state + create repair row + notify | AU-1 |
| A6 | Warranty expiry approaching → notify | date-field approaching → notify | AU-1 |
| A7 | Disposal: gated transition + approval + certificate | AU-10 + request approval + generate document | AU-1 |
| A8 | Current depreciated value on the row | BP-9 formula (date arithmetic over cost, life, acquisition date) | mech:BP-9 |
| A9 | Post disposal/depreciation into the ERP | cross-system process with financial consequence: AU-8 event → Workflow Studio process calls the ERP; not a tier-one job | WS |
| A10 | Annual physical-count campaign report | scheduled (no row context — AU-17's second shape) → generate document over the verification view | AU-1 |
| A11 | Location transfer → notify receiving storekeeper | row updated (location) → notify (recipient from field) | AU-1 |

## 3 · Project management

Shape: Blueprint `project-room`; corporate reference to the project
dimension; corporate figures at project grain (budget, expenditure,
contract/PO counts — N10 guard below); child collections: risks, issues,
tasks, reporting schedule. The risk child gated by PM-3 composition —
the vision's own canonical example, now in a real pilot.

| # | Need | Expression | Verdict |
|---|---|---|---|
| P1 | High-severity risk created → notify PM, require mitigation fields | row created (child) → cond → notify; `required_when: severity = "high"` | AU-1 + mech:BP-3a |
| P2 | Risk not reviewed in 90 days → notify owner | date-field reached → notify | AU-1 |
| P3 | Issue past due → notify + reassign to escalation owner | date-field reached → cond `state != Closed` → notify + assign | AU-1 |
| P4 | Task due date approaching → notify assignee | date-field approaching → notify | AU-1 |
| P5 | Monthly report task + generated meeting pack | scheduled → create row + generate document (DG child iteration, P2) | AU-1 |
| P6 | Expenditure ≥ budget threshold → alert | scheduled → cond over corporate figures → notify (P3 phasing as C6) | AU-1 |
| P7 | Closure gate: no open tasks | rollup `count(tasks where state != Done)` + AU-10 gate `open_tasks = 0` — the gate reads data Frame holds, exactly as AU-10 requires | mech:BP-10 + AU-1 |
| P8 | Engineering task spawns a Jira issue | call webhook (allowlisted, signed) now; IN Jira bidirectional link at P3 | AU-1 |
| P9 | Portfolio view across projects | RP-* reports/dashboards, not automation | mech:RP |
| P10 | Report task overdue → escalate to portfolio office | date-field reached → cond → notify (group) | AU-1 |
| P11 | Risk score = likelihood × impact | BP-9 formula | mech:BP-9 |

## 4 · Fleet management

Shape: **the asset register plus vehicle-specific additions** — the
owner's own framing, and the AC-7/BP-28 proof case: fleet adopts the
asset template with the base locked, extending it with vehicle fields
(plate, odometer, service interval — a one-to-one extension rendered as
columns) and a maintenance-log child collection (one-to-many). No fork,
no upstream change.

| # | Need | Expression | Verdict |
|---|---|---|---|
| F1 | Fleet register derived from asset register | AC-7 template + BP-28 extensions; governance, not automation | mech:BP-28/AC-7 |
| F2 | Service due by date → maintenance row + notify | date-field approaching → create row + notify | AU-1 |
| F3 | Service due by odometer → same | row updated (odometer) → cond `odometer >= next_service_km` → create row + notify | AU-1 |
| F4 | On service completion, set next service point from current reading | state changed → set field `next_service_km = odometer + service_interval` — **requires a computed parameter**, now AU-16 | AU-1\* |
| F5 | Insurance / registration renewals → notify | date-field approaching → notify | AU-1 |
| F6 | Accident report form → issue row, state, notify fleet manager | form submitted → create row + change state + notify | AU-1 |
| F7 | Driver assignment approval | request approval → set field | AU-1 |
| F8 | Monthly fuel consumption report | scheduled (no row) → generate document | AU-1 |
| F9 | Fuel anomaly detection across the fleet | pattern analysis running unattended = Playbook by definition (N4, AI-7); reads via MCP under its own principal | PB |
| F10 | Vehicle in Under repair beyond X days → escalate | as C10 — assemblable today, native shape is the SLA primitive | AU-1 (friction) |

## Tally and verdict

44 needs. **34 (77%) are AU-1 records** — 33 in the vocabulary as
specified, 1 (F4) enabled by AU-16, with AU-17 pinning the sweep
semantics that C4/A3/A10 silently assumed. **7 (16%) are served by
declared mechanisms** (rollup, formula, conditional properties,
overlay/template, reports) — these are automation *requests* a lesser
model would take literally and Frame answers structurally. **2 route out
by design** (A9 → Workflow Studio, F9 → Playbook), which is the
graduation ladder and the AI boundary doing their jobs. **1 (C11)
surfaced a genuine spec question**, now PRD 04's new open question 4.

Of the 37 automation-shaped needs, **36 are expressible (97%)** and the
last is a spec question, not a vocabulary failure. **Zero needs demanded
scripting.** PRD 04 OQ4's gate — ≥80% — **passes**, and the automation
engine (`functions/lib/automations/`) is cleared to build.

## Findings beyond the tally

1. **AU-16 (new, P1)** — computed action parameters. F4's class ("set
   the next service point from the current reading") falls out of a
   literals-only vocabulary and straight into scripting requests.
2. **AU-17 (new, P1)** — sweep triggers fire per row; a scheduled
   trigger without row conditions fires once with no row context. Both
   shapes occur in the pilots; unspecified, the first implementer's
   choice would silently change every date-driven automation's meaning.
3. **SLA primitive evidence** (PRD 04 OQ3): three needs (C10, F10, and
   P3's shape) want elapsed-in-state; all assemblable via stamped dates,
   all cleaner as the P2 primitive. The lean is now evidence-backed.
4. **The N10 guard, stated for the pilots.** "Aggregated fact data" for
   contracts and projects means measures the warehouse publishes **at
   contract/project grain** — Frame reads the column, never computes it
   (vision N10). Amount-paid and amount-committed must exist at contract
   grain, budget and expenditure at project grain; verify against
   `Metadata_Api` before the contract pilot starts.
5. **Carried attributes arrive early or the contract pilot stalls.**
   C2/C6 and the project figures lean on PRD 14's P2 half (carried
   attributes, relationship-constrained pickers). The cheap half (open
   dimension lookups) is Phase 1; the contract register is the argument
   for pulling carried attributes to the front of Phase 2.
6. **Fleet is the extension test.** F1 originally exposed PRD 01's
   overlay-child-collection question; the owner resolved it the other
   way around (BP-28): the adopted base is locked and *all* additions —
   one-to-one field extensions and one-to-many child tables — are
   workspace-local structures rendered transparently. Fleet adopts asset
   without forking, by design.
