# PRD 05: Permissions and Security

## Purpose

Frame's permission system is what separates it from a pile of pretty spreadsheets: ABAC evaluation consistent with our estate, parent-child composition, and the transparency principle (users always know that something is withheld, except where existence itself is masked by deliberate steward choice). All trimming is server-side, on one evaluation path, for every channel.

## Scope

In: permission rule model, evaluation semantics, composition, transparency rendering contract, service principals, audit, export controls, lifecycle enforcement. Out: authentication mechanics (IAP/OAuth, platform standard), Workspace group sync mechanics (PRD 09).

## Model

**PM-1 (P1).** Principals: users (Google identity), Google Groups, workspace roles (owner, editor, viewer per workspace), Blueprint roles (named roles defined in the Blueprint, bound to users/groups per instance context), and service principals (automations, integrations, Workflow Studio, MCP clients), all evaluated identically.

**PM-2 (P1).** Rules live in the Blueprint document: grants of actions (read, create, update, delete, change-state per transition, export, manage) scoped to the whole Blueprint, to row conditions (attribute expressions over the row's fields, e.g. `risk_type = "conduct"`), and to field sets. Effect is allow; absence is deny; explicit deny exists only as a steward tool for carve-outs and always wins. Conditions use the shared grammar.

**PM-3 (P1).** Composition for children: effective child access = parent access AND child rules. Parent access is the ceiling (no child visibility without parent visibility); child rules gate further, including on the child row's own field values. Same engine, one hop of context (the evaluator receives parent row attributes alongside child attributes so rules like "visible to the parent's project manager" are expressible).

**PM-4 (P1).** Evaluation is a single server-side library used by the data service, query engine, search indexer, report engine, document generator, export pipeline, event API fetches, and MCP surface. There is no second implementation anywhere, including the client. The client receives trimmed data plus rendering hints (restricted stubs, withheld counts) and enforces nothing security-relevant.

## Transparency

**PM-5 (P1).** Rendering contract for trimming: withheld fields present as typed restricted stubs (the field exists, its value does not); withheld rows contribute to annotated counts ("N not visible to you") in grids, group headers, rollups, report aggregates, and dashboard metrics; aggregates compute over the full set with the annotation, per the vision principle.

**PM-6 (P2).** Existence masking: per Blueprint or per rule, a steward may mark withheld rows as existence-masked; masked rows are excluded from counts and annotations entirely. Enabling masking is itself an audited event with a required justification, and the Blueprint's catalog entry discloses that masking is in use (the meta-transparency: users can know masking exists on this register without knowing what it hides).

## Security operations

**PM-7 (P1).** Audit log: append-only record of every write (with before/after delta), read of restricted-marked fields, permission rule change, Blueprint version change, export, bound-Sheet generation, and masking toggle. Actor, channel, timestamp, correlation id. Queryable by workspace owners for their scope and by security operations globally; exportable to our SIEM.

**PM-8 (P1).** Export controls: export (CSV, Sheets snapshot, document generation containing restricted fields) is a distinct permission; exports watermark with actor and timestamp where format allows; external-collaborator export is denied by default. Chrome Enterprise Premium watermarking applies at the browser layer for designated URL patterns as per estate policy.

**PM-9 (P1).** Service principals: least-privilege, per-integration identities with scoped grants, rotation, and their actions attributed distinctly in audit ("changed via bound Sheet by X" per the Sheets binding; "by process Payment Approval v3" for Workflow Studio).

**PM-10 (P1).** Sensitivity markers (BP-3) drive defaults: fields marked restricted are excluded from bound Sheets round-trip, from external form status pages, from MCP responses unless the client's grant names them, and trigger read-audit.

**PM-11 (P2).** Access review: quarterly steward-facing review pack per organizational Blueprint (who has what, via which rule, last-used), with one-click revoke proposals. AI-drafted summary of anomalies (PRD 08).

**PM-12 (P2).** Lifecycle enforcement: retention, archival, freeze, and legal hold from BP-21 enforced in the evaluation path (frozen rows reject writes with a clear reason; held rows reject deletion regardless of other rules).

## Non-functional

Evaluation cost must stay inside API budgets: rule compilation per Blueprint version (compiled once, cached), row evaluation O(rules) with attribute lookup from the row itself, target under 5ms per row batch-amortized. Permission changes propagate within 60 seconds everywhere, including search indexes (re-index triggered on rule change).

## Dependencies

PRD 01 (rule schema in Blueprint), PRD 09 (group resolution), all consuming PRDs.

## Open questions

1. Instance-context role binding UX (who binds "project manager" to a person per project row): field-driven (a user field designated as the role source) is the leading design; needs validation with the pilot registers.
2. Search over restricted fields: exclude from index vs index with query-time trimming. Exclude is safer and the default; measure the utility loss.
3. Whether workspace owners can see their workspace's full audit log including restricted-field reads by others, or whether that itself needs a gate. Proposal: gate read-audit visibility to security operations plus the steward.
