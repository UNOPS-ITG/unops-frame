# PRD 12: Notifications

## Purpose

A notifications module baked into Frame, so that everything Frame says to users (automations, approvals, forms, comments, workflow, bound Sheets, system events) is managed centrally within the application: one place for preferences, batching, delivery, and observability, instead of each feature growing its own ad hoc emailer. This is a Frame-internal module, not an enterprise service. If Frame ever needs to participate in an enterprise notifications layer, it does so through this module as the single point of integration (see NT-13); nothing elsewhere in Frame talks to external channels directly. This document supersedes the individual dispatch mentions scattered through PRDs 03, 04, 05, and 09.

## Scope

In: notification model, channels, preferences, digests, actionability, delivery pipeline, storm control, content safety, observability. Out: channel transport internals (Gmail and Chat mechanics live in PRD 09), marketing-style announcements (not a Frame concern).

## Model

**NT-1 (P1).** A notification is a typed event-derived record: notification class (mention, assignment, approval_request, approval_decided, state_change, due_date, form_submission, automation_failure, share, system), subject row/Blueprint reference, actor, recipients (resolved at dispatch from users, groups, roles, or row fields), payload (templated per class), priority (interrupt, normal, digest-eligible), and correlation id linking back to the originating domain event (AU-8). Internally, the module feeds from Frame's own event stream rather than direct calls from each feature, which keeps notification logic in one place; this is an implementation choice for cohesion within Frame, not an enterprise integration statement.

**NT-2 (P1).** Channels at launch: in-app inbox (the canonical record, always written), email, Google Chat. Mobile push arrives with the mobile investment (P3). Channel fan-out per class and per user preference; the inbox entry exists even when other channels are suppressed, so nothing is ever silently lost.

## Preferences and batching

**NT-3 (P1).** Preference resolution, most specific wins: platform defaults per class, workspace overrides (a workspace may raise but not silence approval requests aimed at a user), user preferences per class and channel, and per-row watch/mute. Approvals and direct @mentions are interrupt-class and cannot be muted below the inbox, only channel-shifted; this is stated in the UI rather than discovered.

**NT-4 (P1).** Digests: digest-eligible classes batch per user on a chosen cadence (hourly, twice daily, daily at a chosen hour, workspace timezone aware), grouped by workspace and Blueprint with counts and top items. A quiet-hours window suppresses email and Chat (never the inbox), deferring to the next window.

**NT-5 (P1).** Deduplication and coalescing: repeated events on the same row within a coalescing window collapse ("14 changes to Vendor Register by 3 people"), and a user is never notified of their own actions. Cross-channel dedup: acting on a notification in one channel (approving from Chat) resolves it everywhere within seconds.

## Actionability

**NT-6 (P1).** Approval requests are actionable in every channel: inbox buttons, Gmail action affordances where supported plus a signed deep link fallback, Chat cards (IN-5). Action tokens are single-use, expiring, bound to recipient identity, and the action executes through the standard API path under the actor's identity (never a service shortcut), so PM audit sees the human.

**NT-7 (P2).** Snooze and follow-up: any notification can be snoozed to a time or "when state changes"; snoozed items return to the inbox top.

## Pipeline and operations

**NT-8 (P1).** Dispatch pipeline: event consumer, recipient resolution (group expansion via IN-2, permission check that the recipient can see the subject row before anything is sent), preference resolution, template render, channel dispatch with per-channel retry and dead-letter, delivery status recorded per recipient per channel. Recipient resolution failing closed: a recipient who cannot see the row receives nothing, and the sender-side automation log notes the suppression (transparency for the automation owner without leaking to the recipient).

**NT-9 (P1).** Content safety: notification bodies contain no restricted-marked field values in email or Chat regardless of recipient entitlement (external transports are outside our trim boundary); they carry the row title, class, actor, and a link, with full content behind authentication. The in-app inbox, inside the boundary, may render entitled field context.

**NT-10 (P1).** Storm control: per-user rate ceilings per channel with automatic downgrade to digest on breach and an inbox notice; per-automation ceilings feeding AU-6 failure surfacing; a global circuit breaker for incident response, ITG-operated, with the inbox continuing while external channels pause.

**NT-11 (P2).** Localization: templates externalized, rendered in the recipient's locale (Workspace language preference), Spanish and French first per platform policy.

**NT-12 (P2).** Observability: per-class delivery dashboards (sent, delivered, bounced, acted), automation owners see delivery outcomes for their runs (AU-6), and bounce handling feeds a suppression list with owner alerts. Delivery-failure visibility (decided): workspace owners see aggregate counts only; individual delivery detail is visible to the affected member and to ITG.

**NT-13 (P3).** Enterprise bridge: if an organization-wide notifications layer emerges in the estate, this module is Frame's sole connection point to it, added as one more dispatch channel with the same preference, dedup, and content-safety rules as the built-in channels. No other Frame component integrates with the enterprise layer directly.

## Dependencies

PRD 04 (event stream is the sole input), PRD 09 (Gmail and Chat transports, group expansion), PRD 05 (recipient permission checks, actor attribution for actions), PRD 03 (form submitter confirmations use this pipeline in confirmation-only mode for unauthenticated recipients; status-change notifications for external submitters are opt-in per form, with steward control at organizational tier, decided).

## Open questions

1. Digest rendering surface for Chat (one card vs message per section) pending Chat API layout constraints.
