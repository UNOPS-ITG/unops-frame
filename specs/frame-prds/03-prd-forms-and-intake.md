# PRD 03: Forms and Intake

## Purpose

Forms are Frame's intake edge: the way work enters the system as structured rows instead of email. Every Blueprint can expose forms to staff and, where configured, to unauthenticated external users. A submitted form is a row with a state, an assignee, and a clock.

## Scope

In: form builder, conditional logic, child sections, external publishing, branding, spam and abuse controls, submission routing, submitter follow-up. Out: what happens after intake (PRD 04 automations and workflow), app-level composition of forms (PRD 10).

## Functional requirements

**FM-1 (P1).** Form builder generated from the Blueprint: pick fields, order them, group into pages/sections, set per-field required/read-only overrides (stricter than the Blueprint, never looser), help text, and placeholders. Multiple named forms per Blueprint (a short public form and a full internal form over the same Blueprint).

**FM-2 (P1).** Conditional logic is **declared on the Blueprint field (BP-3a), not per form.** A named form may narrow visibility further — hiding a field the Blueprint shows — but may never reveal a field that BP-3a hides, and may never relax a conditional requirement. This is the same tighten-only rule FM-1 applies to required and read-only overrides, and it is what stops the same capability being authored in two places and drifting. Validation is the Blueprint's single server-side path (BP-4); the form additionally enforces client-side for immediate feedback, but the server is authoritative.

**FM-3 (P1).** Child sections: a form may include a repeatable section bound to a child collection (add another position, add another attachment with metadata), submitted transactionally with the parent per FM-7. Min and max repeat counts are P2.

This is P1 rather than P2 because the phasing was otherwise self-contradictory: FM-7 already requires transactional submission of "parent plus child sections" at P1, GR-17's embedded child grids are already P1, and Phase 1 commits to a pilot with line items — a pilot that, as previously phased, could not accept its own line items through its own intake form. It is also the one capability unmatched at any Smartsheet price tier: no column type creates line items, forms cannot create child records, and their row-level view add-on shows one row's fields rather than a child collection. Phase 1 should ship the thing Phase 1 exists to prove.

**FM-4 (P1).** Internal forms: served to authenticated staff, prefill from identity (submitter user field auto-set), and prefill via URL parameters (validated against field types).

**FM-5 (P1).** External forms: published at a stable URL without authentication. Controls: per-form enable, expiry date, submission cap, CAPTCHA/turnstile, rate limiting per IP, file upload constraints (type allowlist, size cap, malware scan before Drive filing), and a mandatory data-collection notice block (privacy text configured per form, non-removable for external forms).

**FM-6 (P1).** Branding: workspace-level theme (logo, colors) applied to forms; organizational-tier Blueprints may enforce an org-standard theme.

**FM-7 (P1).** Submission handling: submission creates the row transactionally (parent plus child sections), sets the Blueprint's initial workflow state, emits the `frame.form.submitted` event, and triggers any bound automations. Attachments file into the workspace Drive folder per PRD 09 conventions.

**FM-8 (P2).** Submitter follow-up: optional confirmation email with a reference number; optional magic-link status page showing the submitter a configured subset of fields and the current state (fields exposed on the status page are an explicit allowlist, defaulting to state only). No account required.

**FM-9 (P2).** Draft and resume for long external forms via magic link, with drafts expiring on a configured schedule and never entering the Blueprint until submission.

**FM-10 (P2).** Embedding: forms embeddable via iframe snippet on intranet and public pages, with origin allowlist.

**FM-11 (P1).** Accessibility and low bandwidth: forms meet WCAG 2.1 AA, function on mobile browsers, and degrade gracefully on poor connections (chunked attachment upload with resume). Field-office reality is a first-class constraint.

**FM-12 (P2).** A form may expose a **corporate reference** field (PRD 14) so that a submitter picks a real project or country rather than typing one. On an external, unauthenticated form this is permitted **only** for a dimension classified `open`, because an unauthenticated submitter is by definition a principal broader than any warehouse audience.

## Anti-requirements

No form-level logic that writes to other Blueprints (that is an automation's job, keeping side effects in one auditable place). No payment collection in v1. No anonymous editing of existing rows: external participation is one-way, which is narrower than the incumbent, where a free guest shared as editor can edit specific items. Every externally reachable form, embed and status page is inventoried in the PM-13 exposure register by construction, because creating one requires the `publish` action.

## Dependencies

PRD 01 (Blueprint validation, child collections), PRD 04 (events, routing automations), PRD 05 (external submissions execute under a constrained service principal with create-only rights on the target Blueprint), PRD 09 (Drive filing, email dispatch).

## Open questions

1. External file upload malware scanning: GCS quarantine bucket plus scanner service, or a third-party API. Decide with security team; blocking for external forms GA.
2. Multilingual forms: per-form field label translations (steward-entered) vs machine translation with review. Needed early given Spanish and French; proposal is steward-entered with AI draft.
3. Whether the submitter status page (FM-8) constitutes enough of an "external portal" that it should live under the App Composer umbrella instead. Position: keep it in Forms; the composer consumes it later.
