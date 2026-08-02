# PRD 04: Automation and Workflow

## Purpose

Two tiers over one substrate, loosely coupled to Workflow Studio through a published event contract. Tier one gives teams Smartsheet-grade no-code automation they own. Tier two gives the organization real workflow: Blueprint state machines inside Frame, BPMN processes in Workflow Studio, and a mechanical graduation path between the tiers.

## Scope

In: automation model, trigger and action vocabulary, execution engine, the domain event contract, workflow states in Blueprints, process bindings, graduation, observability. Out: BPMN modeling (Workflow Studio's product), AI-driven automation authoring (PRD 08, consumed here).

## Functional requirements

### Tier one: team automations

**AU-1 (P1).** An automation is a structured record, never code: one trigger, optional conditions (shared filter grammar), an ordered action list. Stored versioned alongside the Blueprint, owned by the workspace.

**AU-2 (P1).** Trigger vocabulary at launch: row created, row updated (optionally scoped to named fields), state changed, form submitted, date-field approaching/reached (offset configurable), scheduled (cron-like, workspace timezone), row commented with @mention of a group.

**AU-3 (P1).** Action vocabulary at launch, deliberately closed: set field value(s), assign user, change state (subject to transition rules), notify (email, Chat; recipients from fields, roles, or static), request approval (single approver or any-of group, with approve/reject writing back to a state or field), create row (same or referenced Blueprint, field mapping), generate document (PRD 07), call webhook (allowlisted destinations, signed payloads). The vocabulary is closed on purpose: every action must have a matching Workflow Studio service task so graduation stays mechanical (see AU-12). Adding an action type is a platform decision, not a team setting. No scripting, ever, in tier one.

**AU-4 (P1).** Approvals are first-class: an approval request renders in the approver's Frame inbox, in email with action buttons, and in Google Chat; decisions record actor, timestamp, and comment on the row's activity log; reminders and expiry with fallback action are configurable.

**AU-4a (P2).** Request update — asking a named person, group or user-field value to complete specified fields through a scoped mini-form. This is the incumbent's most-used automation after alerts, and without it the sanctioned answer to "I need Maria to fill in three fields" is emailing her a link and hoping. The response is actioned through the standard API under the responder's own identity, so a responder who cannot write a field sees a stub and the request records a partial response.

Approvals (AU-4) and update requests are two classes of **one pending-task record**, not two mechanisms. That is what makes "what is waiting on me" a single query, makes elapsed-time-in-state a single measurement (which is what open question 3 is really asking for), and makes NT-5's cross-channel resolution mechanically true rather than separately implemented per class.

**AU-14 (P1).** Starter recipes. The platform ships a code-first gallery of recipe templates: complete AU-1 records — trigger, grammar conditions, ordered actions — with named parameters and a sentence-style rendering ("when {date field} is {n} days away, notify {recipient}"). Templates are validated in CI against the trigger and action vocabularies, so a vocabulary change that orphans a template fails the build, never a user. Instantiating a recipe copies it into the workspace as an ordinary AU-1 automation the team owns and edits; afterwards nothing distinguishes it from a hand-built one. The strongest automation product in the field is ahead on packaging, not engine — its recipe gallery is a decade of accreted templates over the same automation-as-data shape AU-1 already commits to — and a gallery of records is the one part of that moat that is cheap to hold, because it is configuration, not capability. AI-1's drafted Blueprints and catalog register patterns may name recommended recipes, so a new register arrives with its obvious automations one click away rather than blank.

**AU-15 (P1).** No self-approval by default. An approval action (AU-4) and a role-gated transition (AU-10) declare `allow_self_approval`, default false. Under the default, the principal whose action created the pending task — directly, or as the actor of the triggering event — cannot be its deciding principal, even where group or role membership would otherwise qualify them; the attempt is rejected naming this mechanism, and the rejection is audited. Segregation of duties is the point of an approval, and a permissive default makes every approval chain's integrity depend on per-team configuration diligence. The reference implementation ships exactly this guard in its workflow engine, which is evidence the strict default is livable in ERP-grade practice.

**AU-16 (P1).** Computed action parameters. Where an action parameter sets a field value, the value may be a literal or a shared-grammar expression at row scope (`odometer + service_interval`, `today() + 90d`), evaluated at execution against the triggering row. This is not scripting and must not be mistaken for a breach of AU-3's closed vocabulary: the grammar is the same closed, analyzable AST every other consumer uses (BP-9), an expression composes no side effects, and validation at automation save refuses out-of-scope accessors exactly as BP-26 does for Blueprints. Without it, the paper catalog's maintenance-scheduling class of needs ("on service completion, set the next service point from the current reading" — `specs/pilots/paper-catalog.md` F4) falls out of the vocabulary and arrives back as scripting requests, which is precisely the pressure N5 must not accumulate. Graduation stays mechanical: an expression parameter maps to an expression on the corresponding Workflow Studio service task input.

**AU-17 (P1).** Sweep semantics for time triggers. Date-field triggers (approaching/reached) and scheduled triggers evaluate as per-row sweeps: conditions are evaluated against each row and one run fires per matching row, idempotent per (automation, row, occurrence), so a delayed sweep never double-fires and a backlog catch-up (AU-5, availability NFR) replays safely. A scheduled trigger with no row conditions fires once with no row context, for needs that are about a view rather than a row ("generate the monthly fleet report"). Both shapes occur in the pilot registers (`specs/pilots/paper-catalog.md` C4, A10); left unspecified, the first implementer's choice would silently change the meaning of every date-driven automation in the estate.

**AU-5 (P1).** Execution: automation runs are asynchronous (Pub/Sub dispatch, Cloud Tasks for scheduled and delayed work), idempotent per triggering event, with retry and dead-letter.

**Loop protection is a named platform guarantee, not an implementation detail:** an automation's own writes are tagged and do not re-trigger the same automation, and cross-automation cascade depth is capped (default 5) with the run halted and flagged beyond it. Both reference implementations are weaker here — one has only local re-entrancy flags and no global cascade cap, the other prevents loops bluntly by refusing sheet-changing actions when the trigger cell holds a cross-sheet formula — so this is a place where the design is ahead rather than catching up, and it should not be quietly traded away for throughput.

**AU-6 (P1).** Observability for owners: per-automation run log (trigger event, condition evaluation result, per-action outcome, duration), failure notifications to the owner, pause/resume, and a dry-run mode that evaluates against a chosen row without side effects.

**AU-7 (P1).** Permissions: automations execute with a workspace service principal whose rights are the intersection of the automation owner's rights at save time and the Blueprint's rules, re-validated on ownership change. An automation can never do what its owner could not.

### The event contract

**AU-8 (P1).** Frame publishes versioned domain events to Pub/Sub: `frame.row.created`, `frame.row.updated` (with field-level delta), `frame.row.state_changed`, `frame.row.deleted`, `frame.form.submitted`, `frame.child.{created,updated,deleted}`, `frame.blueprint.published`, `frame.approval.decided`. Envelope: event id, schema version, correlation id, workspace, blueprint id and version, row id, actor, timestamp, delta. Payloads contain identifiers and deltas, not full trimmed row bodies; consumers fetch details through the API under their own permissions, so the event stream never becomes a permission bypass.

**AU-9 (P1).** The contract is documented, semver-versioned, and additive-by-default; breaking changes require a new major version published in parallel for a deprecation window. Frame neither knows nor throttles for specific consumers; consumer lag is the consumer's problem, with standard Pub/Sub monitoring.

### Tier two: workflow

**AU-10 (P1).** Blueprint state machines: named states, role/attribute-gated transitions (PRD 05 evaluation), transition side effects limited to the tier-one action vocabulary, state history on the row. States drive board lanes (GR-13) and report filters.

A workflow state may declare at most one implied lifecycle status (BP-22), so a transition to Approved submits the row and a transition to Void cancels it. BP-26 refuses a state machine in which any path reaches a submitted state from a cancelled one.

**No external system may block a transition.** Transition gates evaluate only data Frame already holds; where an external fact is required — funds availability before Approved — an integration replicates that fact into a field on its own cadence and the gate reads the field. This is the only answer consistent with the availability NFR ("Frame remains fully functional when Workflow Studio, Playbook, or any integration is unavailable"), with AU-5 and with AU-13, and it is better decided here than under pressure by whoever first receives the request. Note that Frappe found it needed the synchronous case exactly once, special-cased its workflow transition so a failure fails the transition rather than deferring a retry — and that is the shape we are declining.

**AU-3a (P1).** Where the scripting pressure goes. "No scripting, ever" without a named alternative is how a platform grows a shadow estate of Apps Script written against its own API. Three sanctioned routes, and no fourth:

1. **The action vocabulary is code-first with a published contribution process** and a stated review cadence. Adding an action is a platform change with a matching Workflow Studio service task, which is what keeps AU-12 graduation mechanical.
2. **Pre-write extension is a platform capability.** Where an organizational Blueprint needs a pre-write rule BP-4 cannot express, it is a registered, code-first, named validator bound by the platform team and executed inside the single validation path. A validator may read the row, its parent and Blueprint metadata, and accept or reject with a reason. It **may not call an external system**, because BP-4 runs inside the write.
3. **Everything else is a consumer of AU-8 plus the generated API**, outside Frame's process and blast radius.

The evidence for keeping tier one closed is stronger than the PRD originally claimed. Frappe — a developer framework with no obligation to protect users from themselves — ships its server-script capability *disabled* unless an operator sets a flag in a config file outside the application, behind a dedicated role, under a restricted interpreter, with SQL limited to reads and transaction control stripped inside document events. Smartsheet's answer to the same ceiling is a premium tier that runs JavaScript. Both confirm that scripting is a platform-operator capability, not a team setting.

**AU-11 (P2).** Process bindings: a Blueprint may record that an external Workflow Studio process is bound to it (process id, subscription filter reference, display name). Frame renders a read-only process status panel on bound rows, populated via Workflow Studio's API with the viewer's identity. The binding is informational; Frame's behavior does not depend on it. Workflow Studio acts on Frame exclusively through the public API with its own service identity, permission-evaluated like any client. No shared database, no synchronous calls from Frame into Workflow Studio.

**AU-12 (P2).** Graduation: a one-way translation taking a tier-one automation record and producing (a) an event subscription filter from its trigger and conditions, and (b) a BPMN skeleton whose opening service tasks reproduce its action list, handed to Workflow Studio as a draft process. On activation of the process, Frame deactivates the automation and records the binding, atomically from the user's perspective (no window where both or neither run). The translation is possible precisely because AU-3's vocabulary is closed; the appendix of the product vision is the normative narrative for this requirement.

**AU-13 (P2).** Resilience: if Workflow Studio is unavailable, Frame events queue in Pub/Sub and processes catch up; rows show process status as "unavailable" rather than stale data presented as fresh; nothing in Frame blocks.

## Anti-requirements

**No metering.** Automation and workflow execution is never quota'd: no per-workspace run allowance, no per-tier action count, no billable meter on any path. The incumbents meter because automation is their monetization surface — one sells action quotas per month per plan tier, the other caps runs per sheet and per month — and a team that hits an arbitrary allowance mid-month routes around the platform with the tools it was hired away from. Frame has no seats and no plan tiers to defend, so it inherits none of that design pressure. Load and abuse are governed by engineering budgets instead: AU-5 loop protection and cascade caps, NT-10 storm control, AU-6 owner-facing observability, and per-workspace cost attribution on the AI-6 pattern (visibility per AI-13, attribution never billing). Degradation under pressure is queueing and catch-up per the availability NFR, never a denied allowance.

## Dependencies

PRD 01 (blueprint states in metadata, shared grammar), PRD 05 (transition gating, service principals), PRD 07 (generate-document action), PRD 08 (AI-12 recipe authoring targets AU-14's surface), PRD 09 (Chat and email dispatch, webhook signing).

## Open questions

1. Cross-workspace automations (trigger in one workspace, action in another): defer to P3; the honest use cases so far are better served by the event contract plus a consuming service.
2. Approval delegation and out-of-office routing: integrate with a central delegation registry or per-approval fallback only? Proposal: per-approval fallback in P1, delegation registry with HR data in P3 — noting that the organizational directory is itself a corporate dimension (PRD 14), so the registry may be a read rather than a build.
3. SLA clocks as a platform primitive (elapsed time in state, business-hours aware) vs assembled from date triggers. Leaning primitive in P2, and AU-4a's single pending-task record is what makes it one measurement rather than one per class. The paper catalog strengthened the lean: three pilot needs (`specs/pilots/paper-catalog.md` C10, F10, P3) want elapsed-in-state, all assemblable via stamped dates, all cleaner as the primitive.
4. Whether a corporate carried-attribute refresh (PRD 14) fires `row.updated` triggers. Surfaced by pilot need C11 ("upstream contract closed → flag the row"): the refresh is a system write, AU-5 tags automation writes to prevent loops, and nothing yet says which system writes are trigger-visible. Both answers are defensible — triggerable makes upstream drift actionable; silent keeps corporate refreshes out of the automation blast radius — and the choice belongs with PRD 14's sweep cadence design. Owner: platform team, decided alongside PRD 05 open question 3.

## Decisions log

Resolved August 2026:

- **No external system blocks a transition** (AU-10). Folded in rather than left to be discovered, because the first procurement request for a synchronous funds check would otherwise have decided it.
- **Where scripting pressure goes** is now specified (AU-3a) rather than only refused, after confirming that both reference implementations treat scripting as an operator capability rather than a team feature.
- **Approvals and update requests are one pending-task record**, which is what makes elapsed-time-in-state a single primitive.

Resolved August 2026, following the three-competitor discovery run (Smartsheet, Frappe, Monday.com — `specs/discovery/smartsheet-frappe-monday/`):

- **Recipes are a gallery of records, not a builder capability** (AU-14), after verifying that the market leader's automation advantage is template accretion over the same automation-as-data architecture.
- **Self-approval is blocked by default** (AU-15), adopted from the Frappe workflow engine's verified guard.
- **No metering is an anti-requirement, not an accident** — recorded explicitly after documenting both incumbents' quota models.
- **The paper catalog passed** (formerly open question 4): 44 real needs from the four pilot registers, 97% of automation-shaped needs expressible in the closed vocabulary, zero scripting demands; two refinements adopted (AU-16 computed parameters, AU-17 sweep semantics). The automation engine is cleared to build. Full record: `specs/pilots/paper-catalog.md`.
