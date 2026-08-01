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

**AU-5 (P1).** Execution: automation runs are asynchronous (Pub/Sub dispatch, Cloud Tasks for scheduled and delayed work), idempotent per triggering event, with retry and dead-letter. Loop protection: an automation's own writes are tagged and do not re-trigger the same automation; cross-automation cascade depth is capped (default 5) with the run halted and flagged beyond it.

**AU-6 (P1).** Observability for owners: per-automation run log (trigger event, condition evaluation result, per-action outcome, duration), failure notifications to the owner, pause/resume, and a dry-run mode that evaluates against a chosen row without side effects.

**AU-7 (P1).** Permissions: automations execute with a workspace service principal whose rights are the intersection of the automation owner's rights at save time and the Blueprint's rules, re-validated on ownership change. An automation can never do what its owner could not.

### The event contract

**AU-8 (P1).** Frame publishes versioned domain events to Pub/Sub: `frame.row.created`, `frame.row.updated` (with field-level delta), `frame.row.state_changed`, `frame.row.deleted`, `frame.form.submitted`, `frame.child.{created,updated,deleted}`, `frame.blueprint.published`, `frame.approval.decided`. Envelope: event id, schema version, correlation id, workspace, blueprint id and version, row id, actor, timestamp, delta. Payloads contain identifiers and deltas, not full trimmed row bodies; consumers fetch details through the API under their own permissions, so the event stream never becomes a permission bypass.

**AU-9 (P1).** The contract is documented, semver-versioned, and additive-by-default; breaking changes require a new major version published in parallel for a deprecation window. Frame neither knows nor throttles for specific consumers; consumer lag is the consumer's problem, with standard Pub/Sub monitoring.

### Tier two: workflow

**AU-10 (P1).** Blueprint state machines: named states, role/attribute-gated transitions (PRD 05 evaluation), transition side effects limited to the tier-one action vocabulary, state history on the row. States drive board lanes (GR-13) and report filters.

**AU-11 (P2).** Process bindings: a Blueprint may record that an external Workflow Studio process is bound to it (process id, subscription filter reference, display name). Frame renders a read-only process status panel on bound rows, populated via Workflow Studio's API with the viewer's identity. The binding is informational; Frame's behavior does not depend on it. Workflow Studio acts on Frame exclusively through the public API with its own service identity, permission-evaluated like any client. No shared database, no synchronous calls from Frame into Workflow Studio.

**AU-12 (P2).** Graduation: a one-way translation taking a tier-one automation record and producing (a) an event subscription filter from its trigger and conditions, and (b) a BPMN skeleton whose opening service tasks reproduce its action list, handed to Workflow Studio as a draft process. On activation of the process, Frame deactivates the automation and records the binding, atomically from the user's perspective (no window where both or neither run). The translation is possible precisely because AU-3's vocabulary is closed; the appendix of the product vision is the normative narrative for this requirement.

**AU-13 (P2).** Resilience: if Workflow Studio is unavailable, Frame events queue in Pub/Sub and processes catch up; rows show process status as "unavailable" rather than stale data presented as fresh; nothing in Frame blocks.

## Dependencies

PRD 01 (blueprint states in metadata, shared grammar), PRD 05 (transition gating, service principals), PRD 07 (generate-document action), PRD 09 (Chat and email dispatch, webhook signing).

## Open questions

1. Cross-workspace automations (trigger in one workspace, action in another): defer to P3; the honest use cases so far are better served by the event contract plus a consuming service.
2. Approval delegation and out-of-office routing: integrate with a central delegation registry or per-approval fallback only? Proposal: per-approval fallback in P1, delegation registry with HR data in P3.
3. SLA clocks as a platform primitive (elapsed time in state, business-hours aware) vs assembled from date triggers. Leaning primitive in P2; intake use cases keep asking for it.
