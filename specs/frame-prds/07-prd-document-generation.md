# PRD 07: Document Generation

## Purpose

Rows become documents: letters, certificates, memos, meeting packs. One template system shared with Playbook's TipTap-based HTML template editor, merge fields from Blueprint metadata, child-table iteration, e-signature routing, and automatic Drive filing.

## Scope

In: template management, merge model, rendering, output formats, signature routing, filing, generation as an automation action. Out: template editor internals (shared component with Playbook, owned there), free-form document editing (Workspace exists).

## Functional requirements

**DG-1 (P2).** Templates are HTML documents authored in the shared TipTap editor, stored per workspace or per organizational Blueprint (steward-managed for org tier), versioned, with preview against a sample row.

**DG-2 (P2).** Merge model generated from Blueprint metadata: field tokens with format options (dates, currency, user display names), conditional blocks (shared grammar), and repeating blocks bound to child collections rendering as document tables or lists, including nested repetition for grandchildren where the template author dares.

**DG-3 (P2).** Rendering: HTML to PDF (headless Chromium in a rendering service) and native Google Docs output (template mapped to a Docs body via the Docs API) as a P3 option. Rendered output embeds generation metadata (template version, row id, generator, timestamp) in document properties and an optional visible footer.

**DG-4 (P2).** Permission semantics: generation renders with the requesting user's trim; a template referencing fields the requester cannot read fails loudly listing the fields, rather than silently blanking them, unless the template marks a field optional-if-withheld. Restricted-marked fields require the export permission (PM-8) to include.

**DG-5 (P2).** Filing: output files to the row (attachment) and to the mapped Drive folder path convention, named by a configurable pattern (tokens from the row).

**DG-6 (P3).** E-signature (provider decided): Frame integrates through a DocuSign-compatible API client with endpoints configurable at product level (code-first configuration; see the index's configuration architecture section), pointed at our own e-signature product, which follows the DocuSign API surface closely. The integration codes against the DocuSign API contract, so pointing at DocuSign itself or another compatible provider remains a configuration change, not a code change. Flow: route generated PDFs for signature, track envelope status on the row, file the executed copy per DG-5, emit `frame.document.signed`.

**DG-7 (P2).** Generation channels: manual from the row form, bulk from a view selection (per-row documents or one combined pack), and as an automation action (AU-3), all through one rendering service with the same permission semantics (automation generation renders under the automation principal per PM-9).

## Dependencies

Playbook (shared template editor component), PRD 01 (merge model source), PRD 05 (trim and export), PRD 09 (Drive filing, Docs API), PRD 04 (action integration).

## Open questions

1. Template sharing across workspaces below organizational tier (a good letter template is worth sharing without promoting a Blueprint): proposal, a template gallery with the same attribution model as the catalog.
2. Right-to-left and non-Latin script rendering fidelity in the PDF path; test early with Arabic given our field realities.

## Decisions log

Resolved August 2026: e-signature provider (folded into DG-6; DocuSign-compatible client, endpoints as product-level code-first configuration pointed at our own e-signature product).
