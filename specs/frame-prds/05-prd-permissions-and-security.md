# PRD 05: Permissions and Security

## Purpose

Frame's permission system is what separates it from a pile of pretty spreadsheets: ABAC evaluation consistent with our estate, parent-child composition, and the transparency principle (users always know that something is withheld, except where existence itself is masked by deliberate steward choice). All trimming is server-side, on one evaluation path, for every channel.

## Scope

In: permission rule model, evaluation semantics, composition, transparency rendering contract, service principals, audit, export controls, lifecycle enforcement. Out: authentication mechanics (IAP/OAuth, platform standard), Workspace group sync mechanics (PRD 09).

## Model

**PM-1 (P1).** Principals: users (Google identity), Google Groups, workspace roles (owner, editor, viewer per workspace), Blueprint roles (named roles defined in the Blueprint, bound to users/groups per instance context), and service principals (automations, integrations, Workflow Studio, MCP clients), all evaluated identically.

**PM-2 (P1).** Rules live in the Blueprint document: grants of actions scoped to the whole Blueprint, to row conditions (attribute expressions in the shared grammar at the scope permitted by PM-4a, e.g. `risk_type = "conduct"`), and to field sets or sensitivity bands (BP-3b).

*Actions:* read, **select**, create, **import**, update, delete, change-state per transition, export, **publish**, manage. (P2 adds submit, cancel and amend with BP-22 and BP-23.)

- **select** is the right to reference a row of this Blueprint from a reference field, a reference-path formula or a picker, *without* the right to read the register. Pickers resolve only the target's `title_field` and `search_fields` (BP-1a), and a reference-path formula copies only the field it declares. Without this verb, every Blueprint anyone needs to pick from must be readable by everyone who picks, and teams will grow duplicate unrestricted "picker" Blueprints to route around it.
- **import** is distinct from create because bulk creation bypasses the per-row attention that create assumes.
- **publish** is the right to create or modify an externally reachable surface over this Blueprint — published forms (FM-5), embeds (FM-10), status pages (FM-8), composed apps (AC-1), bound Sheets (IN-7 to IN-9). It is the verb PM-13 audits.

The verb vocabulary is code-first configuration; a new verb is a platform decision with a published contribution process, never a steward setting.

*Precedence*, evaluated per (principal, action, row, field): (1) compile all rules whose principal matches the caller, directly or through group or role membership; (2) an explicit deny at any scope beats every allow, and the most specific matching deny is the one recorded in audit and named in the user-facing explanation; (3) otherwise allows union — field-set allows union to a field set, row-condition allows union to a row predicate; (4) absence of any matching allow is denial, with no rule cited; (5) the parent ceiling (PM-3) applies last and unconditionally; (6) there is no evaluation input outside the compiled rule set. Frame has no per-row grants, which is what makes PM-4a's compile-once model sound and PM-11 access review complete by construction.

*Attribute absence.* A condition whose referenced field is null, empty or absent evaluates as **not matched**: an allow grant does not apply to rows with unpopulated attributes, and a deny rule does not fire on them. A rule may set `strict_attributes: true`, under which absence evaluates as matched for deny and unmatched for allow — fail closed. This is distinct from "absence is deny" above, which concerns the absence of a *rule*, not the absence of a *value*.

This clause is not pedantry. BP-15 makes personal-tier fields untyped text until the user types them, so half-populated rows are the designed-for norm at exactly the moment BP-16 and BP-17 promotion attaches rules to them. Frappe shipped both null semantics behind a global switch and defaulted to **fail-open**, so a blank restricted link field makes the row visible to everyone. That is a warning, not a model. BP-17 accordingly reports the absent-value count per rule-referenced field before promotion.

*Verb dependencies*, validated at Blueprint save as BP-26 checks: publish requires read; import requires create; select is implied by read; change-state requires update; export requires read.

**PM-2a (P2).** Principal allow-lists. A row condition may reference a per-principal allow-list of values for a named field — `project in my(:projects)` — materialised per principal and refreshed within the 60-second propagation budget. Allow-list conditions are **always push-downable** (PM-4a), which is what makes them affordable at grid scale where a general attribute expression is not.

This is the recommended form of instance-context role binding: the binding is a stored (principal, field, value, applicable-Blueprints) record rather than an expression, and it may be scoped to named consuming Blueprints, so binding a person to one project narrows that project's Risks and Deliverables without also narrowing Invoices. It closes this PRD's first open question with a decade of production precedent behind the shape.

An allow-list may be **materialised from an organizational dimension hierarchy** (PRD 14), which is how "the regional director sees this office and everything under it" is expressed without Frame maintaining its own copy of the org chart. That capability is separately governed: registering a dimension as a permission source is an elevated right, is audited, and carries a hard staleness bound past which the derived list **freezes and alerts rather than widening**. Warehouse unavailability therefore degrades to stale-but-stable access, never to broadened access.

**PM-3 (P1).** Composition for children: effective child access = parent access AND child rules. Parent access is the ceiling (no child visibility without parent visibility); child rules gate further, including on the child row's own field values. Same engine, one hop of context (the evaluator receives parent row attributes alongside child attributes so rules like "visible to the parent's project manager" are expressible).

**PM-4 (P1).** Evaluation is a single compiled rule set with two generated backends (PM-4a), used by the data service, query engine, realtime channel, search indexer, report engine, document generator, export pipeline, audit-read path, event API fetches, and MCP surface. There is no second implementation anywhere, including the client. The client receives trimmed data plus rendering hints (restricted stubs, withheld counts) and enforces nothing security-relevant.

**Firestore security rules are not a permission surface in Frame and must never be used to express row- or field-level access.** Clients hold no direct store listeners on row data; real-time delivery is server-mediated through rooms whose subscription is itself an evaluated permission decision (GR-8). A client listener would force row conditions and field sets into a second implementation, in a second language, that cannot express PM-3 composition or PM-5 typed stubs at all.

The library is pure: zero I/O, no web-framework and no store-client imports, so every surface can link it. Principal resolution stays strictly outside it. Its output is **data, not a boolean** — allowed actions, readable field ids, restricted field ids, and a `masked` flag that is present and always `false` until PM-6 ships, so existence masking is later an implementation rather than a signature change.

**PM-4a (P1).** Rules compile once per Blueprint version into a single rule AST with exactly two generated backends: an **in-memory row predicate** (data service, document generator, export pipeline, event API fetches, MCP surface) and a **query predicate pushed into the store** (Firestore composite queries; Postgres WHERE clauses for the analytics replica and the search projection). Both are generated from the same AST and covered by a shared conformance suite asserting identical results over a fixture corpus; divergence is a release blocker.

Frappe demonstrates precisely how this fails when it is left unspecified: a Python predicate over a loaded document and a SQL builder over a table are two hook families an application author keeps in sync by hand. Its declarative layer stays cheap only because its row-level mechanism is a value allow-list that compiles to `IN (...)` — which is exactly why PM-2a exists here.

The compiler declares, per rule, whether it is push-downable. The v1 push-downable subset is: equality and set-membership against a scalar field; comparison operators against a number or date field; conjunctions of the above; and any condition whose left-hand side is a principal allow-list (PM-2a). Rules outside the subset are evaluated fetch-then-filter with a bounded over-fetch factor; the query engine then derives page cursors and PM-5 withheld counts from the **evaluated** set, never from the store's own count. A rule that would force fetch-then-filter over an unbounded result set is refused at Blueprint save (BP-26), naming the offending condition.

Because permission trimming makes page yield variable, the cursor returned to a client is the **store cursor of the last document fetched**, never of the last row shown; pages may return short, carrying an explicit over-fetch flag. Getting this backwards silently skips rows.

SR-7's two-stage search trimming is an instance of this compiler rather than a parallel design: the index-time permission envelope is the push-downable projection of the same AST, and the query-time pass is the in-memory backend. PRD 13 is amended to say so.

## Transparency

This is the strongest differentiated idea in the product set, and it has no prior art in either reference implementation, so it will be proposed for deletion as unnecessary complexity by anyone benchmarking against them. Frappe's field trim removes the attribute from the document before serialisation, so the client is never told the field exists, and its counts are computed over the already-filtered query with no residual. Smartsheet has no row- or field-level trimming in its core at all — the add-on that retrofits it simply hides. Every mainstream product answers the aggregate dilemma by choosing silence. Say no.

**PM-5 (P1).** Rendering contract for trimming: withheld fields present as typed restricted stubs (the field exists, its value does not); withheld rows contribute to annotated counts ("N not visible to you") in grids, group headers, rollups, report aggregates, and dashboard metrics; aggregates compute over the full set with the annotation, per the vision principle.

Four rules make this implementable rather than aspirational, and each is cheap now and expensive later:

- **Withheld rows are absent from the row array** and represented only in count pairs — never phantom spacer rows. The two are different virtualization and pagination contracts and cannot be swapped afterwards.
- **Withheld fields are present as typed stubs, never an absent key**, so no renderer ever branches on key existence.
- **Annotations are machine-readable objects, never pre-baked English strings.** The index requires string externalization from day one and six locales; a server-rendered sentence cannot be translated at the client.
- **Field restriction is per cell, not only per column.** PM-2 scopes grants to field sets *and* row conditions, so a field can be visible on rows you own and withheld on rows you do not. GR-6's column stub is the special case where a field is withheld across an entire window.

Page-level and per-fetched-group counts are exact. A view-level withheld total carries an `exact | estimated` discriminator with a stated ceiling, because an exact total requires evaluating every row in the filtered set and that collides with GR-9's 50,000-row windowed requirement. The discriminator lives in the wire schema from the first response so the ceiling stays a configuration value rather than a refactor. The default ceiling is 5,000 rows. What is never acceptable is page-level-only counting presented as a total: the transparency principle is the product thesis, and if the presentation irritates users we change the presentation, never the server-side honesty.

*Where a rule exists to prevent a class of user knowing a row exists, annotation contradicts the rule.* Such rules must be authored as existence-masked (PM-6), and the rule editor states this at authoring time rather than allowing a steward to believe a deny alone suffices.

**Corporate data is the one honest exception** and it is declared rather than discovered. A measure resolved from the warehouse under the viewer's own credentials has been silently trimmed by BigQuery, and BigQuery will not tell Frame what it filtered — so Frame cannot compute over the full set, and cannot annotate what was withheld. Such values carry a different, explicit annotation: *computed under your own warehouse entitlements*. See PRD 14.

**PM-5a (P2).** Explanation surface. A user meeting a restricted stub or a withheld count may see the *name* of the deciding rule, the Blueprint, and the steward to ask — never the withheld value and never the row's attributes. The explanation is generated by the PM-4a evaluator as a by-product of the deciding rule, not by a second component reasoning about rules.

**PM-6 (P2).** Existence masking: per Blueprint or per rule, a steward may mark withheld rows as existence-masked; masked rows are excluded from counts and annotations entirely. Enabling masking is itself an audited event with a required justification, and the Blueprint's catalog entry discloses that masking is in use (the meta-transparency: users can know masking exists on this register without knowing what it hides).

## Security operations

**PM-7 (P1).** Audit is a family of typed, append-only event classes on one stream with a class discriminator — one write path and one query surface, not four stores.

- **Change:** writes with before/after field-level delta, including child rows by collection and position, rendered as human-readable diffs rather than raw JSON. This is the class GR-5's activity history and NT-4's digests read.
- **Access:** reads of fields at or above the restricted threshold (BP-3b), exports, print and document generation, bound-Sheet generation and refresh.
- **Governance:** permission rule changes, Blueprint versions, promotion and demotion decisions, masking toggles, freeze, legal hold and retention actions, naming-counter resets (BP-25), corporate-data source registration and permission-source designation (PRD 14), service-principal creation and rotation, and creation or modification of any externally reachable surface (the `publish` action).
- **Auth:** sign-in, impersonation, service-principal use.

Every class carries actor, channel, timestamp and correlation id, is queryable by workspace owners for their scope and by security operations globally, and is exportable to our SIEM per class.

Change-class records derive from the AU-8 event contract like any other consumer. Access-class and auth-class records have no AU-8 event and are therefore the one sanctioned direct-write path into audit; they are batched off the request path and must not consume the PM-4 evaluation budget.

**Retention is declared per class**, as code-first configuration, with a per-Blueprint override that may only lengthen. Governance-class records are exempt from retention and survive row deletion and Blueprint deprecation. Access-class records default to 24 months. Change-class retention follows the Blueprint's own retention policy (BP-21) and never expires before the rows it describes. No retention rule may remove a record covered by a legal hold, whatever its class. Change-class capture is unconditional at team and organizational tier and may be reduced to state-changes-only at personal tier.

Without this, PM-7 mandates an unbounded store — every write with a delta, every restricted read, forever — which is the first thing an audit function asks about and the first cost line that surprises operations. Frappe separates these classes for exactly this reason, and makes its version history opt-in per document type because unconditional change capture routinely exceeds the size of the data it describes.

**The audit-read path is a registered PM-4 consumer** and delta entries are field-trimmed with the same `Decision`: a restricted field's before/after renders as "changed (value withheld)". Otherwise the activity drawer becomes a channel that hands out precisely the values PM-10 says should trigger a read-audit.

**PM-8 (P1).** Export controls: export (CSV, Sheets snapshot, document generation containing restricted fields) is a distinct permission; exports watermark with actor and timestamp where format allows; external-collaborator export is denied by default. Chrome Enterprise Premium watermarking applies at the browser layer for designated URL patterns as per estate policy.

**PM-9 (P1).** Service principals: least-privilege, per-integration identities with scoped grants, rotation, and their actions attributed distinctly in audit ("changed via bound Sheet by X" per the Sheets binding; "by process Payment Approval v3" for Workflow Studio).

**PM-10 (P1).** Sensitivity markers (BP-3) drive defaults: fields marked restricted are excluded from bound Sheets round-trip, from external form status pages, from MCP responses unless the client's grant names them, and trigger read-audit.

**PM-11 (P2).** Access review: quarterly steward-facing review pack per organizational Blueprint (who has what, via which rule, last-used), with one-click revoke proposals. AI-drafted summary of anomalies (PRD 08).

**PM-12 (P2).** Lifecycle enforcement: retention, archival, freeze, and legal hold from BP-21, and the submittable lifecycle from BP-22 and BP-23, enforced in the evaluation path (frozen and submitted rows reject writes with a clear reason naming the governing mechanism; held rows reject deletion regardless of other rules).

**PM-13 (P2).** External exposure register. PM-11 reviews grants per Blueprint; nothing yet answers "what of ours is reachable from the internet right now, and who owns it". The register is an always-current inventory of every published form (FM-5), embed and origin allowlist (FM-10), magic-link status page (FM-8), published app (AC-1), active bound-Sheet binding (IN-7 to IN-9) and outbound webhook destination (IN-12), each with owner, audience, last activity and a one-click revoke. Entries are created only through the `publish` action (PM-2), so the register is complete by construction rather than by diligence. PM-11's quarterly pack renders that workspace's rows from it.

## Anti-requirements

**No per-row grants.** Frame has no mechanism to let one person see one row. This is deliberate and it is what makes PM-4a's compile-once evaluation sound and PM-11 access review complete by construction: a per-row grant could only be a second evaluation input consulted alongside the compiled set — on every read, on every channel, in the search query path and in the replica's consumers — which is the second permission implementation PM-4 forbids, arriving as a feature rather than as a mistake. Both reference implementations have one (Frappe's document share, Smartsheet's item sharing) and both use it as the escape hatch that makes their access model unreviewable.

The sanctioned alternative is an instance-scoped role binding (PM-2a) added by a steward — a rule like any other, so it appears in access review, it can expire, and it is audited. Service target: under one working day. Product documentation describes the refusal and the alternative together, because a refusal without a named alternative is how a platform grows a shadow estate of spreadsheets emailed around it. Revisit only with measured evidence that the binding path is being routed around via export.

**No sharing that grants.** A view is a lens, never a grant (GR-11), and a dashboard tile trims per viewer (RP-5). Smartsheet's dashboard report widget explicitly shows data to viewers not shared to the source sheets; Frame offers no such bypass at any tier. A migrating team must instead be granted a scoped read, which is the honest form of what the bypass was doing implicitly. This difference is named in product copy and in IN-14's migration report, so it arrives as a documented decision rather than a "the dashboard is broken" ticket.

## Non-functional

Evaluation cost must stay inside API budgets: rule compilation per Blueprint version (compiled once, cached), row evaluation O(rules) with attribute lookup from the row itself, target under 5ms per row batch-amortized. Permission changes propagate within 60 seconds everywhere, including search indexes (re-index triggered on rule change).

That 60-second budget also binds the denormalised parent attributes child rows carry so that PM-3 evaluation needs no additional reads (PRD 01 data model notes). On a parent write, the engine diffs the rule-referenced attribute set and enqueues a bounded, idempotent child re-stamp through a named system-write path that emits no domain events and writes one aggregate audit entry. A stale denormalised parent attribute is a silent permission leak, so this fan-out is a first-class deliverable rather than an optimisation.

## Dependencies

PRD 01 (rule schema in the Blueprint; BP-3b sensitivity bands are what grants are scoped against; BP-26 validates rule coherence at save), PRD 09 (group resolution), PRD 14 (dimension hierarchies as a PM-2a allow-list source, and the corporate-data exception to PM-5), PRD 02 (GR-8's server-mediated realtime is what keeps PM-4 true on the wire), all consuming PRDs.

## Open questions

1. Whether workspace owners can see their workspace's full audit log including restricted-field reads by others, or whether that itself needs a gate. Proposal: gate read-audit visibility to security operations plus the steward.
2. Whether the PM-5a explanation surface should name the deciding rule to *all* viewers or only to those holding some grant on the Blueprint. Naming a rule discloses that a rule exists and roughly what it keys on, which is intended under the transparency principle but may be too much on a register where the rule name itself is sensitive. Proposal: rule name for any viewer holding read on the Blueprint; steward contact only otherwise.
3. Whether PM-2a allow-lists materialised from a corporate dimension should be recomputed on a schedule, on an upstream change event, or both. Both is correct but doubles the machinery; a schedule alone risks a 24-hour window on a revoked assignment. Proposal: event-driven with a scheduled reconciliation sweep, decided with PRD 14's sweep cadence.

## Decisions log

Resolved August 2026, following a review against the Frappe Framework source and the Smartsheet product:

- **Instance-context role binding** (formerly open question 1) resolves to PM-2a principal allow-lists — a stored record rather than an expression, always push-downable, scopable to named consuming Blueprints.
- **Search over restricted fields** (formerly open question 2) resolves to exclusion, consistent with SR-6, which already records the same decision and accepts the utility loss.
- **The action vocabulary gains `select`, `import` and `publish`**, the first because reference pickers otherwise force over-granting, the third because PM-13 needs a verb to audit.
- **Attribute-absence semantics are specified explicitly** and default to fail-open-for-allow, fail-closed-for-deny, with an opt-in strict mode — after finding that Frappe's equivalent defaults to making a row with a blank restricted field visible to everyone.
- **Audit becomes typed classes with per-class retention**, because a single unbounded log was the specification's largest unpriced cost.
