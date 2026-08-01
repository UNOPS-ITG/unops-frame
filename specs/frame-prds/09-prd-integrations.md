# PRD 09: Integrations

## Purpose

Deep, not decorative: Google Workspace as the estate's fabric, bound Sheets as the governed escape hatch, Atlassian as the delivery bridge, plus webhooks, import/export, and migration tooling. Patterns follow Bob 2.0: user-consented OAuth where acting as the user, least-privilege service identities where acting as the platform.

## Scope

In: Drive, Sheets (three binding modes), Docs, Gmail, Calendar, Chat, Groups; Jira, Confluence; webhooks; import/export; Smartsheet migration. Out: MCP (PRD 08), event contract (PRD 04).

## Google Workspace

**IN-1 (P1).** Drive: workspace-to-folder mapping created on workspace creation, row attachments stored in a per-Blueprint subfolder, generated documents filed per DG-5. Permission granularity (decided): the default contract is per-Blueprint, meaning the subfolder ACL matches "anyone with any read access to this Blueprint," managed one-directionally Frame to Drive; Drive is never the permission source of truth. True per-row mirroring applies only to Blueprints that carry row-level permission rules. Serving model (decided): attachments on rows governed by row-level rules, and attachments containing restricted-marked content, are proxy-only, stored without user-facing Drive ACLs and served exclusively through Frame with the row permission checked on every download; all other attachments are native Drive files with the per-Blueprint ACL and full Drive affordances (preview, Drive search, Docs commenting). A Blueprint acquiring row-level rules migrates its attachments to the proxy path as part of the rule change. Drift posture (decided): a periodic sweep detects out-of-band Drive shares on Frame-managed files; Frame does not auto-revert. Detected shares are logged in the audit trail and notified to the workspace owners and the Blueprint's managers, with a single-click revert action in the notification and in a drift review panel; Reverting is a human choice, recorded with actor and timestamp. Proxied attachment previews (decided): Frame renders its own inline previews for images and PDF on the proxy path; other formats in the proxied class are download-only.

**IN-2 (P1).** Groups: permission principals resolve Google Groups with membership cached and refreshed (target staleness under 15 minutes) plus push refresh where the Admin SDK allows; group resolution failures fail closed.

**IN-3 (P2).** Gmail. Sender identity (decided): all platform-generated mail sends from a single platform address (frame@unops.org), with the originating workspace carried in the display name ("Frame: Procurement Intake") and identified in the body; no per-workspace mailboxes, no domain-wide delegation for sending, no send-as-user for automations. Reply capture (decided): header-based matching. Outbound Message-IDs are stored against the row; an intake mailbox receives replies and matches In-Reply-To/References headers to thread the reply onto the row's conversation, with a short reference token in the subject line as the fallback matcher for forwards and header-stripping clients; unmatched mail lands in a triage queue for the workspace, never silently dropped. The intake mailbox (decided) is a Workspace mailbox read via the Gmail API under a scoped service identity. Deliverability (decided): mail sends from the primary unops.org domain, no dedicated subdomain; in compensation, outbound volume is protected by the notification module's storm controls (NT-10) and per-automation ceilings (AU-5), bounce and complaint rates are monitored with alerting, and a platform-level send circuit breaker exists so a misfiring automation cannot damage the shared domain reputation. Create-row-from-email for designated intake addresses remains in scope, attachments filed per IN-1.

**IN-4 (P2).** Calendar: designated date fields sync to a chosen team calendar (one-directional Frame to Calendar in P2, bidirectional for designated booking Blueprints in P3).

**IN-5 (P2).** Chat: notification delivery, actionable approvals (AU-4) via Chat cards, and a Frame Chat app for quick queries routed through ask-this-view under the asking user's identity.

**IN-6 (P3).** Docs: embed live Frame views via published smart-chip/link previews where API support allows; degrade to a rich link card otherwise.

### Bound Sheets (the 5a design, normative here)

**IN-7 (P2).** Snapshot: "Open in Sheets" generates a Sheet from the current view containing only the requester's trimmed rows and fields, in their Drive, tagged with binding metadata, registered in the binding service, marked mode=snapshot. No sync back. Restricted-marked fields require export permission and are excluded by default.

**IN-8 (P2).** Live-read: snapshot plus scheduled or on-demand refresh (full re-render of the bound range; user formulas outside the bound range survive, edits inside it are overwritten on refresh with a cell-note warning applied at generation). Refresh re-evaluates permissions each time; access loss converts the binding to a frozen snapshot with a notice.

**IN-9 (P3).** Round-trip: edits within the bound range are ingested as proposed changes through the import pipeline: revision attribution resolves the editing user via Drive revisions (accepting its coarseness; ambiguous attribution routes the change to review rather than applying), each change validates against the Blueprint under that user's permissions, clean changes apply with "via bound Sheet" attribution (PM-9), failures and conflicts (Frame-side edits since last sync) queue in a reviewable exceptions surface for the binding owner. Gating: team tier by default, organizational tier by steward opt-in, never on restricted-marked fields. Structural damage to the bound range degrades the binding to snapshot with an explanatory notice. Telemetry: bindings per Blueprint, round-trip share of edits, exception rates, reported to product (the "escape hatch must not become the front door" metric).

## Atlassian

**IN-10 (P3).** Jira: link a Frame row to Jira issues (and JQL-scoped issue sets), pull status/assignee/dates into designated read-only fields on a refresh cycle, push creation of a Jira issue from a row with field mapping, and reflect Jira transitions as row events for automations. Authentication via OAuth app as in Bob 2.0; per-workspace connection configuration.

**IN-11 (P3).** Confluence: embed live Frame views in Confluence pages (Frame macro/iframe with viewer authentication), generate Confluence pages from rows via templates (DG pipeline, Confluence storage-format output), link Blueprints to their documentation pages shown in the Blueprint info panel. Embed trimming (decided): embeds must honor per-viewer trimming; where Confluence's caching behavior prevents per-viewer rendering, embedding is restricted to Blueprints without row-level rules, verified during IN-11 implementation.

## Webhooks and import/export

**IN-12 (P1).** Outbound webhooks: per-Blueprint subscriptions to the event vocabulary, HMAC-signed payloads, retry with backoff, destination allowlist administered by ITG. Inbound: authenticated ingestion endpoint per Blueprint (service-principal credential) accepting create/update batches through the single validation path.

**IN-13 (P1).** Import: CSV and Sheets import with mapping UI, type coercion preview, validation dry-run, and an exceptions report; imports are the same pipeline round-trip uses (build once).

**IN-14 (P3).** Smartsheet migration tooling: API-based extraction of sheets, columns, and rows into draft Blueprints with type inference, attachment transfer to Drive, and a report of non-portable features (cross-sheet links become reference suggestions, automations become tier-one drafts where mappable). Also targets legacy internal trackers.

## Dependencies

Bob 2.0 integration patterns and OAuth apps, PRD 04 (events), PRD 05 (principals, export permission), PRD 07 (Confluence output), binding service (new, this PRD's main engineering artifact alongside the import pipeline).

## Decisions log

Resolved August 2026: sender identity, reply capture, and deliverability posture (folded into IN-3, including the intake mailbox as a Workspace mailbox read via the Gmail API under a scoped service identity); Drive granularity, the proxy/native serving split, drift posture, and proxied previews (folded into IN-1); Confluence embed trimming (folded into IN-11). No open questions remain in this PRD.
