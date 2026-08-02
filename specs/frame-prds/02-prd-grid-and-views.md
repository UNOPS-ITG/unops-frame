# PRD 02: Grid and Views

## Purpose

The grid is the product. This PRD specifies the Frame grid, the view system (Gantt, board, calendar, timeline), master-detail forms, and saved views. The quality bar is explicit: if Maya does not find this faster and pleasanter than a Google Sheet for tracker work, Frame fails regardless of everything else. Component selection is PRD 11; this PRD defines what the component must deliver.

## Scope

In: grid interaction model, editing, selection, clipboard, row hierarchy, child grid embedding, view types and morphing, saved views and sharing, master-detail form rendering, presence and co-editing, performance budgets. Out: permission semantics (PRD 05, consumed here), formula language (PRD 01), dashboards (PRD 06).

## Functional requirements

### Grid core

**GR-1 (P1).** Keyboard-first editing: arrow navigation, Enter to edit, Escape to cancel, Tab across, type-to-replace, F2-equivalent edit-in-place, undo/redo stack (50 steps minimum, scoped to the user's own changes).

**GR-2 (P1).** Range operations: multi-cell selection, fill-down and fill-right with pattern continuation for dates and sequences, copy/paste interoperable with Google Sheets and Excel clipboard formats (TSV plus HTML clipboard flavor), paste validation with a per-cell error surface (invalid cells highlighted, valid cells applied, summary toast with an exceptions review).

**GR-3 (P1).** Columns: resize, reorder, freeze, hide, per-view configuration. Rows: variable height for rich text and multi-line, row hierarchy with indent/outdent **where the Blueprint declares itself hierarchical**, drag reorder within permission. Hierarchy is a declared property of the Blueprint rather than a grid setting, which is what stops it being confused with parent-child composition (open question 4) at the point where the confusion would otherwise be made.

**GR-4 (P1).** Cell renderers and editors per field type (all BP-2 types), including user pickers resolving the directory, reference pickers with typeahead search into the target Blueprint, **corporate reference cells resolving against an organizational dimension** (PRD 14, rendering the stored label snapshot with a staleness marker where the key has been retired upstream), attachment cells showing Drive thumbnails, and select cells with colour chips drawn from the option display attributes declared once on the field (BP-2).

A reference picker requires only the `select` action on the target Blueprint (PM-2), not `read`, and resolves only the target's `title_field` and `search_fields` (BP-1a). Without that distinction every Blueprint anyone picks from must be readable by everyone who picks.

**GR-5 (P1).** Row-level surfaces: comment thread per row (with @mentions producing notifications), attachment panel, activity history, and workflow state control, opened in a right-hand detail drawer without leaving the grid.

Activity renders as human-readable deltas — "Ingrid changed Risk Rating from Medium to High" — never as raw change records, and is trimmed by the same evaluator as everything else, so a field at or above the restricted threshold renders as "changed (value withheld)" (PM-7). Selecting a cell exposes **that cell's history** in one interaction: previous value, new value, actor, timestamp and channel (grid, form, API, import, bound Sheet, automation). The delta is already stored; this is a rendering requirement, not a new capture. History for a restricted-threshold field is visible only to principals entitled now, and viewing it is an access-class audit event.

**GR-6 (P1).** Restricted rendering per the transparency principle: withheld columns render as a labeled restricted column stub (not silently absent); withheld rows are represented in counts and group headers as "N not visible to you"; aggregate footers annotate.

**GR-7 (P2).** Grouping by any field with collapsible groups and per-group aggregate footers; multi-level sort; filter bar with the shared filter grammar plus a natural-language filter box (PRD 08 native AI).

**GR-8 (P1).** Real-time: edits by others appear within 2 seconds, cell-level presence indicators (avatar chip on the cell being edited), conflict rule is last-write-wins per cell with the losing writer notified inline and offered their value back. No document-level locking.

"No document-level locking" is a **write-granularity requirement, not a UX preference**: a whole-row save cannot express last-write-wins per cell, so writes are field-scoped and carry a per-field version stamp from the first write. PM-7's before/after delta and AU-8's field-level delta both presuppose the writer knows which fields changed, so all three requirements share one mechanism.

**Real-time delivery is server-mediated: the client subscribes to server-defined rooms, never to the store.** Subscription to a room is itself a permission decision evaluated by the PM-4 library before it is accepted, and payloads on a room are trimmed by that same library. **Firestore security rules are not a permission surface in Frame and must never be used to express row- or field-level access** — a client listener would force ABAC into a second implementation, in a second language, that cannot express PM-3 composition or PM-5 typed stubs at all.

### Performance budgets (hard requirements)

**GR-9 (P1).** 10,000 loaded rows with 30 columns: scroll at 60fps on a mid-range laptop, cell edit commit under 100ms perceived, view open under 1.5s p95. 50,000 rows via windowed server fetch: scroll remains smooth with skeleton cells, no interaction over 200ms. Budgets are CI-enforced with an automated performance harness from Phase 1 week one, not retrofitted.

**GR-10 (P1).** Accessibility: full keyboard operability, screen reader row/cell announcement, visible focus, WCAG 2.1 AA. This is a component-selection constraint (PRD 11) and a release gate.

### Views

**GR-11 (P1).** Saved views per Blueprint: name, view type, filters, sorts, grouping, column set, and sharing scope (private, workspace, link-shared within permission). Views are permission-trimmed at render; sharing a view never extends data access (a view is a lens, not a grant).

**GR-12 (P2).** Gantt: bars from start/end or start/duration field mappings, drag to reschedule, dependency links (finish-start at minimum; the other three types P3) with constraint propagation, baselines (snapshot and variance display), critical path highlight, working-calendar awareness (org holiday calendar from Workspace).

**GR-13 (P2).** Board: cards grouped by any select/user/state field, drag between lanes performing the underlying field or state change (state changes respect workflow transition permissions and fail visibly if disallowed), card templates showing chosen fields, WIP indicators.

**GR-14 (P2).** Calendar: month/week views from date fields, drag to move, multi-day spans, overlay of multiple Blueprints in one calendar (P3).

**GR-15 (P2).** Timeline: lightweight horizontal timeline for portfolio-style rendering, lane per grouping value.

**GR-16 (P1).** View morphing is lossless and instant: switching view types never alters data and preserves filter context. Every view type consumes the same trimmed row stream.

### Master-detail forms and child grids

**GR-17 (P1).** Parent-child Blueprints render as a generated master-detail form: header fields laid out from view defaults (steward-configurable layout: sections and columns), each child collection as an embedded grid beneath, with add/remove/reorder inline. Embedded child grids are the same grid component with the same budgets, trimmed by composed permissions. **Conditional visibility comes from BP-3a and is not separately authored here** — it is declared once on the field so that every renderer, the API and the import path agree.

**GR-18 (P2).** Grandchildren render as expandable rows within the child grid (one level of expansion in the form; deeper navigation opens the child's own detail form).

**GR-19 (P1).** The form and the grid are two renderings of the same row: opening a row from the grid slides in the detail form; edits in either surface sync live.

### Formatting, connections, and one non-goal

**GR-20 (P1).** Conditional formatting: ordered, named rules that set cell background, text colour, text weight or a whole-row highlight when a condition in the shared grammar is met. Rules are declared in view configuration and optionally as a Blueprint view default (BP-1a), inherited by new views and narrowable but not wideable by a saved view. They evaluate top-down with first match winning per target, and travel with a saved view when it is shared (GR-11). Formatting applies in the grid and in embedded child grids at P1, and in board, calendar and Gantt as those views land.

This is not a nicety. It is a core, non-premium capability of the incumbent and the main reason its grid is legible at a glance, and this PRD's own stated bar is that a grid 80% as good as Smartsheet's kills adoption.

Conditions evaluate at row-plus-subject scope (PM-4a), so `assigned_to = me` is expressible, and are evaluated **server-side alongside the row's trim**. Formatting must not become a side channel around trimming: a restricted column stub (GR-6) is never formatted from a value the viewer cannot read, and a rule whose condition references a field the viewer cannot read is skipped for that viewer rather than returned as colour. Colour computed from a value you may not see is a disclosure channel, and this is the cheapest moment to close it.

**GR-21 (P2).** Connections. Where a Blueprint declares reverse links (BP-1b), the detail drawer and the master-detail form render a grouped section listing rows elsewhere in the estate that reference this one, with lazily-fetched counts annotated per PM-5 and a pre-filled action to create a new related row. Groups the viewer holds neither `read` nor `select` on are **omitted entirely** rather than shown as zero — a zero count over an unreachable group is itself a disclosure.

**GR-23 (P1).** Row actions. Every grid row carries an actions affordance on the frozen primary column — reachable however far the grid scrolls, because an action hidden behind horizontal scrolling is an action that does not exist at 40 columns. The vocabulary is closed and code-first (the AU-3 pattern), and the actions a principal cannot take on a row are absent, never disabled — the server's PM-4 rendering hints decide, the grid renders. The first and universal action is **Open**: the row opens as its *form view* — the GR-17 master-detail record page, read-only, with an explicit **Edit** action whose saves go through the same field-scoped write path as the grid (BP-4: the form view is a caller of the one writer, never a peer) — with child collections as embedded tables and one-to-one additions (BP-19/BP-28 extensions) as fields in their own sections. Open is fundamental because a grid is where rows are *found* and a record is where a row is *read and worked*; a product that conflates the two is a grid with chrome, which is the failure the August 2026 reframing names. Further actions — duplicate (honouring BP-3 `no-copy`), generate document (DG-1), request update (AU-4a) — join the same vocabulary as their engines land.

**GR-22 (P1, non-goal).** **No cell-anchored formulas.** Formulas are field-level; there is no per-cell expression site. A per-cell expression makes a column whose meaning varies by row: no Blueprint describes it, no API can type it, no report can aggregate it honestly, no document merge can resolve it, no permission rule can reason about it, and it breaks silently on row insert. It is the single most likely request from a migrating Smartsheet user, which is exactly why it is recorded as a numbered non-goal rather than left as an open question that the first migration will appear to settle.

The alternatives, which cover the real need: field formulas (BP-9), reference-path formulas for pulling a related record's value onto the row (BP-9a), rollups over children and relationships (BP-10), and bound Sheets (IN-7 to IN-9) for genuinely personal analysis, where cell formulas belong and are the user's own business. It is worth noting what the incumbent's cell-link model costs in practice: a published ceiling of 100 distinct cross-sheet references per sheet, and a large-scale mode that raises the row cap only by disabling cross-sheet references altogether.

## Non-functional

Offline: not supported in v1; the grid degrades to read-only with a banner on connectivity loss, queuing nothing (honest failure over silent divergence). Mobile: responsive read-and-light-edit for grid and forms in v1; full mobile editing is P3. Print/export: any view exports to CSV and to the bound-Sheets snapshot (PRD 09).

## Dependencies

PRD 11 decides the rendering engine. PRD 01 supplies metadata driving renderers and layouts. PRD 05 supplies the trimmed row stream and composed child permissions. PRD 04 consumes state changes made through views.

## Open questions

1. Grouped-by-state board vs workflow: when a board lane is a workflow state, is drag a transition request (with approval steps possibly pending)? Position: yes, drag creates the transition attempt and the card shows pending state if the transition has gates.
2. Concurrent structural edits (two admins editing the Blueprint while users edit rows): resolution model needed; likely Blueprint edits apply on a short debounce with active-user notification.
3. Whether conditional formatting rules should be expressible over a *corporate* reference's carried attributes (PRD 14) as well as over local fields. Attractive — "highlight rows whose project is in a red-flagged portfolio" — but it makes formatting depend on a snapshot's freshness. Proposal: allow it over carried attributes, which are materialised on the row, and never over live-resolved values.
4. Rows whose sort field is empty vanish under that sort. Discovered 2026-08-02 building the register overview: Firestore's orderBy excludes documents missing the ordered field, so a row that has never had a value for the sorted column disappears from the result set with no warning — `plan.unsortable` is null because the slot legitimately exists. This contradicts the register's own "a sort silently did nothing is the least debuggable UI" stance, one level down. Candidate answers: stamp a typed sentinel into every slot at write time (nulls-last by construction, costs a backfill), or have the reader run a second missing-field pass and append (costs a query and complicates cursors). Owner: whoever builds the next reader iteration; must be decided before saved views with sorts are promoted as shareable truth.

## Decisions log

Resolved August 2026:

- **Cell-anchored formulas** (formerly open question 1) are promoted from an open question to a numbered non-goal, GR-22. "Revisit only under strong user evidence" was an invitation the first Smartsheet migration would have accepted in week one.
- **Row hierarchy versus parent-child** (formerly open question 4) is answered structurally rather than by onboarding copy: hierarchy is a declared Blueprint property (GR-3), so the choice is made once in the model rather than repeatedly in the grid.
- **Conditional formatting** is added as GR-20 at P1, having been absent from the entire spec set.
- **Real-time is server-mediated** (GR-8): no client store listeners on row data, ever.

Resolved August 2026, from the owner's directives during the vision checkpoint:

- **Row actions are a grid fundamental** (GR-23), with **Open → the form view** as the universal first action: the record page is the row's primary reading surface, the grid its finding surface. Added by owner directive after the composition correction; the frontend preview implements Open and Edit ahead of the engine.
