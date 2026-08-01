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

## Dependencies

PRD 01 (blueprint states in metadata, shared grammar), PRD 05 (transition gating, service principals), PRD 07 (generate-document action), PRD 09 (Chat and email dispatch, webhook signing).

## Open questions

1. Cross-workspace automations (trigger in one workspace, action in another): defer to P3; the honest use cases so far are better served by the event contract plus a consuming service.
2. Approval delegation and out-of-office routing: integrate with a central delegation registry or per-approval fallback only? Proposal: per-approval fallback in P1, delegation registry with HR data in P3 — noting that the organizational directory is itself a corporate dimension (PRD 14), so the registry may be a read rather than a build.
3. SLA clocks as a platform primitive (elapsed time in state, business-hours aware) vs assembled from date triggers. Leaning primitive in P2, and AU-4a's single pending-task record is what makes it one measurement rather than one per class.

## Decisions log

Resolved August 2026:

- **No external system blocks a transition** (AU-10). Folded in rather than left to be discovered, because the first procurement request for a synchronous funds check would otherwise have decided it.
- **Where scripting pressure goes** is now specified (AU-3a) rather than only refused, after confirming that both reference implementations treat scripting as an operator capability rather than a team feature.
- **Approvals and update requests are one pending-task record**, which is what makes elapsed-time-in-state a single primitive.
