# PRD 01: Blueprint Engine

## Purpose

The Blueprint engine is Frame's foundation: the metadata service that defines what everything else renders, validates, permissions, and automates. Every other PRD depends on this one. It must make the Frappe DocType idea invisible to Maya, powerful for Daniel, and governable for Ingrid.

## Scope

In: Blueprint schema definition, field types, validation, relationships, parent-child composition, computed fields, versioning, provenance and attribution, the promotion ladder, the catalog, the AI-assisted promotion review, lifecycle policies. Out: rendering (PRD 02), permission evaluation semantics (PRD 05), event publication details (PRD 04).

## Functional requirements

### Blueprint definition

**BP-1 (P1).** A Blueprint is a versioned JSON document in Firestore defining: identity (id, name, description, icon, tier, workspace), fields, relationships, children, permission rules, workflow states and transitions, computed fields, view defaults (BP-1a), lifecycle policies, and provenance. The schema of the Blueprint document itself is versioned independently (metaschema version) so the engine can migrate old Blueprints forward.

Migrating them forward is a mechanism, not an intention: metaschema migrations are an ordered, run-once-per-environment ledger of code-first migrations applied under a lock, each declaring whether it runs *before* the engine reads Blueprints under the new metaschema (migrations that must read the old shape) or *after*, with each phase committed or rolled back as a unit and the running step observable. The pre/post split is invisible until it is violated. A no-op v1-to-v2 migration is registered and exercised in CI before anything needs migrating, so the first real one is not written under pressure against live Blueprints.

**BP-1a (P1).** View defaults are a named set, not a phrase. A Blueprint declares `title_field` — rendered wherever a row is named, which is to say reference chips, breadcrumbs, notification subjects, search results, generated document filenames and audit entries, and therefore mandatory at team tier and above — plus `subtitle_field`, `search_fields` (what a reference picker's typeahead matches), `default_sort`, `default_columns` (derived from BP-3 surfacing properties), `icon` and `colour`. Fields declared `indexed`, every field named in a declared reverse link (BP-1b), and every field referenced by a permission rule automatically generate the required Firestore composite and Postgres index definitions; users are never asked to reason about indexes.

**(P2, shipping with each view type.)** Per-view-type field maps: calendar (start, end, all-day, title), Gantt (start, end, progress, dependencies, milestone flag, colour), board (lane field), timeline (lane field, start, end). A field map is a Blueprint-level default, one per view type. A user wanting a second calendar over a different date pair creates a saved view (GR-11) of type calendar and overrides the mapping there — GR-11 is already the named, shareable, permission-trimmed rendering object and there is no second one. A view type is offered only where its map is satisfiable; unsatisfiable view types are hidden with an inline explanation naming the missing field, never rendered empty.

**BP-1b (P2).** Reverse links. A Blueprint declares which other Blueprints' reference fields point at it, optionally grouped, so that "what else in the estate points at this vendor?" has an answer without anyone building a view. Declarations are verified at save time by BP-26 and drive index generation per BP-1a. Rendering is GR-21.

**BP-2 (P1).** Field types at launch: text (single, long, rich), number (integer, decimal, currency with ISO code, percent), date, datetime, **time** (time of day without a date, which scheduling and booking registers need and a datetime cannot express), duration, boolean, single select, multi select, user (resolving Google identity), group (resolving Google Group), attachment (Drive-backed), URL, email, phone, reference (link to a row of another Blueprint), **corporate reference** (a value from an organizational dimension, PRD 14), rollup (aggregate over a relationship or child collection), formula (computed, BP-9), created/modified stamps.

The type registry is code-first application configuration, so adding a type is a platform decision with a published contribution process rather than a steward setting.

Single select and multi select carry per-option display attributes — colour, optional icon, display order — and an optional `render_as` of `chip` or `glyph`, where `glyph` selects a named glyph family (traffic-light ball, harvey ball, flag, star, priority arrow) that fixes the option set. The stored value is always the option key, never the glyph. These attributes drive grid colour chips (GR-4), board lane colours and ordering (GR-13), conditional-formatting defaults (GR-20) and chart series colours (RP-4): a status vocabulary is coloured once in the model, not reconfigured per view, per board and per dashboard.

Auto-number is deliberately **not** a field type; a row's human-readable identifier is a Blueprint-level declaration (BP-25), because it is a governance artifact people quote in audit findings rather than a column somebody happened to add.

**P2 adds:** multi-reference (many-to-many to another Blueprint, which the singular reference type cannot express — "the stakeholders on this project" is not one row), **corporate figure** (a measure from an organizational fact at a declared grain, PRD 14), geolocation, rating, barcode, JSON (escape hatch, admin-gated).

**P3 adds:** polymorphic reference, where the target Blueprint is itself determined by a companion field on the row, for the genuine cases where an attachment or a note belongs to either a project or a contract. Deferred because it complicates every consumer — index generation, the search projection, the replica schema and reverse links all have to reason about a target that is not known statically — and the demand should be demonstrated before that cost is paid.

**BP-3 (P1).** Every field declares an explicit property set; the property registry is code-first configuration. At launch:

- *Identity and type:* name, label, type, target or options, precision, min and max, non-negative, length.
- *Constraints:* required, unique (within a declared scope), not-null, **set-once** (immutable after first write — reference numbers and contract identifiers need this and a whole-row freeze is too blunt an instrument), default, declarative validation rule (range, regex, length, allowed values, cross-field conditions expressed in the shared grammar).
- *Write control:* read-only, **no-copy** (excluded when a row is duplicated or amended, BP-24).
- *Display:* hidden, help text, placeholder, default column width and order, **translatable** (per-field, because select option labels and help text have to render in six UN locales and a UI string table cannot reach user-authored content).
- *Conditionality:* visible-when, required-when, read-only-when (BP-3a).
- *Surfacing defaults:* in default grid columns, in the standard filter bar, searchable (consumed by SR-6), indexed.
- *Governance:* sensitivity band (BP-3b), exportable.

Enabling `unique`, enabling `not-null`, or tightening any validation rule runs a scan of existing rows at save time and refuses if current data violates it, reporting the offending rows. This check is mandatory at BP-16 promotion, which is exactly when dirty personal-tier data is being typed for the first time.

**BP-3a (P1).** Three conditional properties on every field, expressed in the shared grammar at row-plus-parent scope — the same parent accessor PM-3's child evaluator uses, not a second one: `visible_when`, `required_when`, `read_only_when`. Section and group containers additionally support `collapsed_when`. Expressions are predicates; assignment is rejected at Blueprint save (BP-26).

Subject and environment attributes are out of scope here: a field's visibility must not depend on who is looking, because PM-5 owns per-viewer trimming and two mechanisms for hiding a field would make a governed withholding indistinguishable from a layout rule.

Every renderer consumes these declarations and **no renderer defines its own conditional-logic authoring surface** — the grid and its cell editors, embedded child grids, the master-detail form (GR-17), forms (FM-2), document generation conditional blocks (DG-2), and the generated OpenAPI description. This is a reduction in surface area, not an addition: authoring the same capability in the form builder and again in view-default layout guarantees drift, and leaves conditional requiredness unenforced on the API and import paths, which contradicts BP-4. Where a field is non-writable by both BP-3a and a permission rule, the rejection names the governing mechanism in that order.

**BP-3b (P1).** Sensitivity is an integer band (0 = plain, ascending); the band vocabulary is code-first configuration and declares one named **restricted threshold**. PM-2 grants are per (principal, action, band), so a principal may hold read at band 1 and write only at band 0 — an access shape a three-value marker cannot express — and field access becomes a set-membership test per action rather than a per-field rule evaluation, which is what makes PRD 05's sub-5ms budget reachable.

Every existing rule that keys on "restricted" is redefined once against the threshold and not restated per consumer: PM-10 exclusions and read-audit, SR-6 index exclusion, IN-7 and IN-9 bound-Sheet exclusion, NT-9 notification content safety, DG-7 watermarking. Changing the threshold is a platform decision with an estate-wide re-index, not a steward setting. PM-2's named field sets remain available where bands cannot express the requirement, carrying their higher evaluation cost explicitly.

**BP-4 (P1).** Declarative validation is evaluated server-side on every write regardless of channel (grid, form, API, import, bound Sheet, automation). There is exactly one validation path.

That path begins by restoring, from the store, the stored value of every field the writing principal cannot write, before any validation rule is evaluated. Restricted stubs (PM-5) are never a value: they are never accepted from a request body on any channel, are never coerced to a type default, and are not writable by a client round-trip, an import file carrying a stub column, an automation replaying a fetched row, or a bound Sheet whose generated range contains one. Where a caller submits a value for a field they cannot write, Frame rejects the write naming the offending fields rather than silently ignoring or reverting them; the grid and forms may pre-emptively render such cells non-editable using PM-4 rendering hints, but the server decides and the rejection is audited.

This clause is not hypothetical. Frappe shipped the same masking mechanism and immediately hit both failure modes: numeric field types casting the placeholder back to zero on serialisation, and clients posting the placeholder straight back on save, overwriting real data. Its fix was to re-read true values from the store on every save, which is what the first sentence above requires.

The same single-declaration principle governs conditional display: there is exactly one place a field's visibility, conditional mandatoriness and conditional read-only state are declared (BP-3a).

### Parent-child composition

**BP-5 (P1).** A Blueprint may declare named child collections, each referencing a child Blueprint. A child row belongs to exactly one parent row. Deletion, archival, and freeze cascade from parent to children. Save of a parent with modified children is transactional (Firestore subcollection writes within a batch/transaction, parent as the boundary).

**BP-6 (P2).** Children may declare their own children (grandchildren). Depth is capped at 3 levels; the cap is a product decision to keep UI and query complexity sane, revisited only with a concrete use case that survives scrutiny.

**BP-7 (P1).** A parent may declare multiple child collections (a project with milestones, risks, and stakeholders). Each collection has its own child Blueprint, ordering rule, and permission composition per PRD 05.

**BP-8 (P2).** Child rows are also queryable flat across parents ("all deliverables due this month"), served by a collection-group index, with parent context joined into results and parent-permission ceilings enforced.

### Computed fields and formulas

**BP-9 (P1).** Formula fields support row-scope expressions (arithmetic, string, date, logical, conditionals) over the row's own fields, evaluated server-side. The formula language is a single, documented grammar shared with permission row conditions (PM-2), automation conditions (AU-1), form conditional logic (FM-2), conditional field properties (BP-3a), report filters (RP-1), document conditional blocks (DG-2) and field-qualified search terms (SR-3). One language, everywhere.

**Expressions persist as versioned AST JSON, never as strings.** The string is an editor affordance and a readback, not the stored artifact. This is cheap now and ruinous later: with eight consumers, changing the grammar once expressions are stored as text means a regex migration across user-authored permission rules, saved-view filters, formula fields and form conditions simultaneously.

The grammar's scope set is defined once as code-first configuration and enforced by BP-26. *Row scope* — the row's own fields — is available to formula fields, declarative validation, document merge conditions and rollup filters. *Row-plus-parent scope* adds one hop of parent-row attributes and is available to child permission rules (PM-3) and conditional field properties (BP-3a). *Row-plus-parent-plus-subject-plus-environment scope* adds the acting principal's attributes and group memberships, principal allow-lists (PM-2a), and evaluation time, and is available only to permission rules, view and report filters, automation conditions and search terms. **A field whose value is materialised, replicated or indexed may never be computed above row-plus-parent scope**; the validator refuses it, naming the offending accessor. A materialised value that varies by reader is not a value, it is a bug with a schema.

A formula field declares `materialized: true` (the default; evaluated on write and stored) or `materialized: false` (evaluated at read time from fields in row scope, not stored, no column). A read-time formula cannot be filtered, sorted, grouped or indexed on, is excluded from the Postgres replica (RP-7) and the search projection (SR-6), and BP-26 refuses one that any saved view, report, permission rule, replica or index references. A materialised formula requires a backfill of every row whenever the expression changes, and until that backfill completes the affected rows are flagged rather than served as correct.

**BP-9a (P2).** Reference-path formulas. A formula field whose expression is a single reference-path term — `vendor.country` — is a lookup: materialised, and therefore filterable, sortable, groupable, exportable, indexable and searchable like any materialised formula, obeying BP-11's one-hop limit. This is by far the most-used denormalisation in practice and the mechanism that makes a normalised model usable in a flat grid; without it, "put the vendor's country on the contract row" has no expression, since BP-9 covers own-row values and BP-10 covers aggregates over children.

It carries two properties no other formula has. `overridable` (default false; when true the expression evaluates only where the local value is blank, so a user may deliberately override). And a **mandatory immediate backfill with progress reporting** when the field is added to a Blueprint that already has rows — rows are never readable as stale. Reading a reference-path formula requires the `select` action on the target Blueprint (PM-2), not `read`. Changing the source is a breaking change under BP-12.

This is not a third derived-value mechanism; it is BP-9 with a declared shape, so BP-11's dependency graph, BP-12's change classification and RP-7's schema generation continue to handle exactly two kinds of computed field. The equivalent over an organizational dimension rather than another Blueprint is a carried attribute, specified in PRD 14 and deliberately built on this same shape rather than a parallel one.

**BP-10 (P2).** Rollup fields aggregate over a child collection or a reference relationship: count, sum, min, max, avg, latest, concat, and filtered variants. Recalculation is event-driven via the dependency graph (see BP-11) with eventual consistency target under 5 seconds p95.

**BP-11 (P2).** The engine maintains a formula dependency graph in Postgres for promoted Blueprints (and in-memory for team tier), detecting cycles at Blueprint save time and rejecting them with a comprehensible error. Cross-Blueprint formula references are limited to one relationship hop in v1 (vision risk note: conservative scope is deliberate).

### Versioning and provenance

**BP-12 (P1).** Every Blueprint edit creates a new version with author, timestamp, and a structural diff; Blueprints are never mutated in place. Rows record which Blueprint version they were last validated against. Non-breaking changes (adding optional fields, relaxing validation) apply immediately.

A named whitelist of provably lossless type transitions — code-first configuration, modelled on Frappe's equivalent but authored for our own type system — is treated as non-breaking and applies immediately. Every other type change is **refused at P1** with an explanation naming the transition.

Breaking changes (removing fields, tightening validation) require an explicit `migration` block that dry-runs and reports which rows would fail, then applies with default-fill or quarantine-to-exceptions. `transform` — the arbitrary-expression remediation — is the expensive third of this requirement and defers to P2. Refusing all breaking changes outright for a whole phase would be worse than this: the escape hatch then becomes an engineer editing Firestore by hand, which produces no version, no audit entry and no revalidation stamp, which is precisely what the audit trail exists to prevent.

**BP-13 (P1).** Provenance metadata: original author, contributors (anyone whose Blueprint edit was accepted), forked-from lineage, AI-assistance flags per BP element. Provenance is append-only.

**BP-14 (P1).** Attribution surfaces: the catalog entry and the Blueprint's info panel display the credit line ("thanks to the work of X, Y") and adoption stats (workspaces using it, row count governed, forks). Credit is never removable by promotion; stewards may add contributors, never delete the original author.

### Promotion ladder

**BP-15 (P1).** Tiers and their contracts. Personal: private to the creator, minimal ceremony, fields may be untyped text until the user types them. Team: shared within a workspace, fields must be named and typed, appears in workspace search. Organizational: published to the catalog, steward-approved, replicated to Postgres, eligible for event contract consumers, subject to data standards.

**BP-16 (P1).** Promotion from personal to team is self-service with an inline typing wizard (AI-assisted field type inference from existing data, user confirms).

**BP-17 (P2).** Promotion to organizational tier opens a review case for the domain steward containing the AI-prepared working file: catalog similarity scan with field-by-field diff against nearest matches, naming and type normalization suggestions against our data standards, inferred validation rules from actual team-tier data, permission gap flags (fields that look sensitive but are unrestricted, informed by field content classification), and a draft migration plan for look-alike trackers. The steward approves, approves with changes, requests changes, or rejects, all recorded. The working file also includes BP-26's full validator output, and a Blueprint that fails validation cannot enter promotion review. It reports, per field referenced by any permission rule, the count of existing rows whose value for that field is absent; promotion requires that count to be zero or explicitly accepted by the steward with a recorded reason, since those rows will behave differently under the rule than the steward expects (PM-2 attribute-absence semantics). Promotion is a database-level act: the approved Blueprint publishes to the environment's catalog directly, with no deployment involved (per the index's configuration architecture section, user-authored artifacts at every tier are data, not code-first config). Target: under 30 minutes of steward attention for a routine case; median promotion cycle under 5 working days, measured and reported.

**BP-18 (P2).** Demotion and deprecation: organizational Blueprints can be deprecated (no new instances, existing continue) with a designated successor and a migration assist. Nothing is deleted while rows reference it.

### Catalog

**BP-19 (P2).** The catalog is browsable and searchable by name, domain, field semantics ("has a vendor field", "tracks risks"), and steward. Each entry shows description, credit line, adoption stats, version history, and a one-click "use this" that **binds the workspace to the upstream Blueprint rather than copying it**.

There is one Blueprint document; a subscribing workspace stores only its deviations, as overlay records of two kinds: added fields, namespaced to the workspace and forbidden from colliding with upstream names now or in future versions; and property overrides on upstream fields and on Blueprint-level view defaults. **Overrides may only tighten, never relax.** A workspace may make an optional field required, narrow a select's options to a subset, hide a field, raise a sensitivity band, add a validation rule, or reorder columns. It may not clear a required flag, widen validation, lower a sensitivity band, change a field's type, or change a naming rule kind. Permission rules are overlayable in one direction only: a workspace may add deny rules and narrow the row conditions or field sets of an inherited grant; it may never add a grant, widen an inherited grant's scope, or remove an inherited deny. The overridable property list and the tighten-only rules are code-first configuration.

Upstream version bumps then apply to every subscriber automatically, because there is nothing to merge. Where a new upstream version invalidates an overlay — an overridden field removed, a narrowed option withdrawn — both steward and workspace are notified, and the workspace continues on its previous upstream version until it resolves the conflict. A workspace may **fork** instead of subscribe: a one-way exit, credit line preserved (BP-14), no further upstream updates, visibly marked as a fork in the catalog's adoption stats.

The alternative — instantiate a copy with a subscription for schema updates — is fork-with-subscription, and once a workspace modifies its copy every upstream update becomes a three-way merge nobody performs. That is precisely the Control Center pathology this product exists to end, rebuilt inside it. It would also break BP-12 versioning (which version is a fork on?), BP-14 adoption stats, and RP-7's schema generation, which would become N schemas per catalog entry.

Firestore layout: a subscribing workspace stores an overlay at `workspaces/{ws}/blueprintOverlays/{bp}`, not a Blueprint copy. The engine merges upstream plus overlay at metadata load, once, so every consumer — grid, API, validator, evaluator, indexer, replicator — sees one resolved Blueprint and no consumer performs its own merge.

**BP-20 (P2).** Duplicate pressure: when a user creates a new team-tier Blueprint, the engine runs the similarity scan and, above a threshold, suggests the catalog entry instead ("This looks like Vendor Register, used by 14 teams"). Suggestion, never a block.

**BP-27 (P2).** Overlay convergence. The engine reports, per catalog entry, where subscribing workspaces' overlays (BP-19) have independently converged — the same added field name, the same tightened property — with workspace counts, surfaced to the steward as fold-in candidates feeding the BP-17 working file and the next upstream version. Overlays are structured records, so convergence is a query, not telemetry archaeology. This is the catalog's growth loop: an overlay three workspaces wrote independently is the estate telling the steward what the base Blueprint is missing, and without the report that signal accrues silently per workspace — the reference implementation's equivalent overlay records accumulate per site for years precisely because nothing aggregates them upstream. The report is a suggestion surface only; folding a field in remains an ordinary BP-12 version with BP-17 review where required.

### Lifecycle

**BP-21 (P2).** Lifecycle policies per Blueprint: retention period, archival rules (archived rows leave active indexes but remain auditable), freeze (row becomes immutable, e.g. after approval), and legal hold override. Enforcement is server-side and logged. For Blueprints declaring the submittable lifecycle (BP-22), submission *is* the freeze mechanism and correction happens through amendment (BP-24), never through unfreeze-edit-refreeze.

### Submission, cancellation and amendment

The largest conceptual gap between a Blueprint and a DocType, and the one most specific to us. A frozen row is a dead end: once an approved purchase memo turns out to be wrong, BP-21 offers only "stay frozen forever" or "unfreeze", and unfreezing destroys the integrity claim that made freezing worth having. The legal reality for the documents this platform is meant to hold is that you do not edit an approved record — you cancel it and issue an amendment carrying a link back. Phased deliberately: retrofitting an immutability dimension onto live rows is brutal, so only the reserved slot is P1.

**BP-22 (P1 — reserved slot; P2 — enforcement).** The metaschema defines a `lifecycle` block with an optional `submittable` declaration, and every row carries a `lifecycle_status` field (draft, submitted, cancelled). No Blueprint may declare itself submittable before P2; the field exists from P1 so no backfill is ever needed. From P2, a submittable Blueprint's legal transitions are exactly draft→draft (save), draft→submitted (submit), submitted→submitted (restricted update per BP-23), and submitted→cancelled (cancel). Draft→cancelled, submitted→draft, and any transition out of cancelled are rejected by the single evaluation path on every channel including import, bound Sheets, automations and the generated API. A Blueprint declares **either** the submittable lifecycle **or** a BP-21 freeze policy, never both; BP-26 refuses the combination. Submittable is for records corrected by amendment; freeze is for records corrected not at all.

**BP-23 (P2).** Fields on a submittable Blueprint carry `editable_after_submit` (default false). A submitted row rejects writes to any field or child collection not so marked, naming the field and the lifecycle status. New child rows in an `editable_after_submit` collection are permitted; edits to existing ones follow the field rule. Where a field is non-writable by both BP-23 and BP-3a, the lifecycle reason is reported.

**BP-24 (P3).** Amendment. A cancelled row may be amended: Frame creates a new draft row of the same Blueprint carrying an immutable `amended_from` reference to the cancelled predecessor, copying all fields except those marked `no_copy` (BP-3). The predecessor is never edited. Lineage renders on both rows, travels into document generation (DG-2), audit (PM-7) and search (SR-6), and is queryable.

Submit, cancel and amend publish `frame.row.submitted`, `frame.row.cancelled` and `frame.row.amended` on the AU-8 contract, additive under AU-9; the amendment event carries the predecessor id so search, notifications and the Postgres replica render lineage without a second integration seam.

### Row identity and naming

**BP-25 (P1 for the declaration; P2 for series).** Rows are keyed internally by an opaque, immutable, server-generated id that is never displayed and never reused. The **display identifier** is a separate Blueprint-level declaration, because for a UN agency the record identifier is a governance artifact people quote in audit findings, emails and paper — not a column somebody happened to add.

At P1 the declaration supports `opaque` (show the internal id) and `by_field` (a designated field's value is the identifier, with uniqueness enforced per BP-3). At P2 it adds a `series` rule with a dotted expression such as `PO-.YYYY.-.MM.-.####`, whose counter is keyed on the **evaluated prefix** so that resetting monthly or per-office works as authors expect. A series supports preview-without-consuming, so a form can show what the identifier will be without burning a number on an abandoned draft, and any counter reset is an audited governance event (PM-7).

### Blueprint validation

**BP-26 (P1).** Blueprint coherence validation. Saving a Blueprint runs a named check suite and refuses the save with a per-check message identifying the field. This is Frame's **only** Blueprint-time validator: the PM-2 verb-dependency checks, the BP-16 and BP-17 attribute-absence promotion counts, the BP-1b reverse-link verification, the BP-9 grammar scope-set enforcement and the BP-22 lifecycle-exclusivity check are all checks in this one suite, reported in one output. The suite is code-first configuration and every new Blueprint-level capability ships its validator checks in the same change. It runs on overlay save as well as Blueprint save (BP-19), evaluated against the merged upstream-plus-overlay document.

This matters doubly because BP-16 and BP-17 have an **AI drafting the model**: an unguarded AI-generated Blueprint with a hidden required field and no default is a Blueprint nobody can ever save a row against, and it will be reported as a platform bug rather than a modelling mistake.

Launch checks: field names unique, valid identifiers, and not colliding with reserved system names; layout containers cannot be required; hidden-and-required-without-default refused; `unique` permitted only on types where it is meaningful and only after a duplicate scan passes; long-text and rich-text fields cannot be `indexed`; a select's default must be one of its options and a boolean's default must be a boolean; precision within range and not greater than declared length; a reference field's target exists, is reachable by the workspace, and is not this Blueprint's own child; a child collection's target is a declared child Blueprint and the BP-6 depth cap holds; BP-3a conditional expressions are predicates over in-scope fields and are not self-referential; a `required_when` that can be true while `visible_when` is false is refused; formula and rollup dependencies acyclic (BP-11); `title_field`, `search_fields`, `default_columns` and every declared view field map reference existing fields of the correct type; permission rules reference existing fields and declared actions.

## Data model notes

Firestore layout:

```
workspaces/{ws}/blueprints/{bp}                                # metadata
workspaces/{ws}/blueprintOverlays/{bp}                         # BP-19 deviations, never a copy
workspaces/{ws}/rows/{bp}/items/{rowId}                        # rows
workspaces/{ws}/rows/{bp}/items/{rowId}/children/{childId}     # children; collectionId is a FIELD
```

Two details are load-bearing. The `items` segment is not decoration: Firestore paths alternate collection and document, so `workspaces/{ws}/rows/{bp}/{row}` is five segments and names a *collection*, not a row document. And using **fixed collection ids** (`items`, `children`) with `collectionId` carried as a field on the child — rather than a collection per named child collection — means one collection-group index set covers every Blueprint that will ever exist, and BP-8's flat cross-parent query becomes a collection-group query filtered on `collectionId`. The alternative multiplies index definitions per Blueprint against a hard per-database ceiling.

Row documents carry an opaque server-generated id (BP-25), `lastValidatedBlueprintVersion` (BP-12), and soft-delete tombstones. Child documents denormalise `workspaceId`, `blueprintId`, `tier`, `collectionId`, `parentId` and the parent attribute values referenced by composed permission rules, which is what keeps PM-3 evaluation free of additional reads inside an embedded child grid under GR-9's budgets — at the cost of an invalidation fan-out that PRD 05 owns. Organizational Blueprints are additionally registered in a root `catalog` collection. Postgres receives normalized replicas for organizational tier (PRD 06 owns the replication pipeline; this PRD owns the "children as related tables" mapping generated from Blueprint metadata).

## API

Generated per Blueprint from metadata: CRUD for rows and children (child operations addressable both nested and flat), query endpoint honoring the shared filter grammar, metadata read, OpenAPI spec published per Blueprint version. Admin API for Blueprint CRUD, promotion, and catalog. All APIs enforce PRD 05 evaluation.

## Dependencies

PRD 05 (permission rule schema is part of the Blueprint document; PM-4a compiles the rules this PRD stores; BP-3b's bands are what PM-2 grants against), PRD 08 (AI inference and similarity scan), PRD 06 (Postgres mapping), PRD 04 (events emitted on Blueprint and row changes), PRD 14 (corporate reference and corporate figure field types, and carried attributes built on BP-9a's shape), PRD 02 (GR-21 renders BP-1b reverse links; GR-20 consumes BP-2 option colours).

## Open questions

1. Metaschema governance: who approves changes to the Blueprint schema itself (new field types)? Proposal: ITG platform team with steward consultation, quarterly cadence. BP-1 now specifies *how* a metaschema change is applied; this question is only about who decides.
2. Similarity scan implementation: embedding-based field semantics vs structural diff heuristics, or both. Spike alongside PRD 08.
3. Whether team-tier Blueprints should support formulas referencing organizational Blueprints (governance asymmetry). Initial position: read-only references allowed, rollups not.
4. Whether a workspace overlay (BP-19) may add a *child collection* to a subscribed organizational Blueprint, or only fields. Adding one is structurally a schema change to the upstream document rather than a property override, and it interacts with RP-7's generated replica schema. Initial position: fields and property overrides only; a workspace needing its own child collection forks. **No longer hypothetical:** the fleet pilot is the asset register plus vehicle fields *plus a maintenance-log child collection* (`specs/pilots/paper-catalog.md` F1) — under the initial position, the flagship AC-7 template-plus-overlay proof case forks instead. Either the position moves for this case, or the asset template ships with maintenance as an optional upstream collection. Decide before the fleet pilot's template is authored.

## Decisions log

Resolved August 2026, following a review against the Frappe Framework source and the Smartsheet product:

- **Unique constraint scope** (formerly open question 3) is a per-field declared scope, folded into BP-3, rather than a per-Blueprint global-or-instance switch.
- **Auto-number is not a field type**; row display identifiers are a Blueprint-level declaration (BP-25).
- **Catalog adoption binds rather than copies** (BP-19), because fork-with-subscription reproduces inside Frame the Control Center pathology the vision criticises.
- **Expressions persist as AST, never strings** (BP-9), because eight consumers make a later text migration untenable.
- **Conditional field behaviour is declared once on the field** (BP-3a) rather than separately in the form builder and the layout editor, which also closes the hole where conditional requiredness went unenforced on the API and import paths.

Resolved August 2026, following the three-competitor discovery run (`specs/discovery/smartsheet-frappe-monday/`):

- **Overlay convergence reporting** (BP-27) closes the loop BP-19's bind-not-copy adoption opened: the overlay mechanism was already specified here before the run; what the Frappe evidence added is that overlays without upstream aggregation diverge silently for years.
