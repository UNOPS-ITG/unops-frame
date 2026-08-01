# PRD 02: Grid and Views

## Purpose

The grid is the product. This PRD specifies the Frame grid, the view system (Gantt, board, calendar, timeline), master-detail forms, and saved views. The quality bar is explicit: if Maya does not find this faster and pleasanter than a Google Sheet for tracker work, Frame fails regardless of everything else. Component selection is PRD 11; this PRD defines what the component must deliver.

## Scope

In: grid interaction model, editing, selection, clipboard, row hierarchy, child grid embedding, view types and morphing, saved views and sharing, master-detail form rendering, presence and co-editing, performance budgets. Out: permission semantics (PRD 05, consumed here), formula language (PRD 01), dashboards (PRD 06).

## Functional requirements

### Grid core

**GR-1 (P1).** Keyboard-first editing: arrow navigation, Enter to edit, Escape to cancel, Tab across, type-to-replace, F2-equivalent edit-in-place, undo/redo stack (50 steps minimum, scoped to the user's own changes).

**GR-2 (P1).** Range operations: multi-cell selection, fill-down and fill-right with pattern continuation for dates and sequences, copy/paste interoperable with Google Sheets and Excel clipboard formats (TSV plus HTML clipboard flavor), paste validation with a per-cell error surface (invalid cells highlighted, valid cells applied, summary toast with an exceptions review).

**GR-3 (P1).** Columns: resize, reorder, freeze, hide, per-view configuration. Rows: variable height for rich text and multi-line, row hierarchy with indent/outdent where the Blueprint enables it, drag reorder within permission.

**GR-4 (P1).** Cell renderers and editors per field type (all BP-2 types), including user pickers resolving the directory, reference pickers with typeahead search into the target Blueprint, attachment cells showing Drive thumbnails, and select cells with color chips.

**GR-5 (P1).** Row-level surfaces: comment thread per row (with @mentions producing notifications), attachment panel, activity history, and workflow state control, opened in a right-hand detail drawer without leaving the grid.

**GR-6 (P1).** Restricted rendering per the transparency principle: withheld columns render as a labeled restricted column stub (not silently absent); withheld rows are represented in counts and group headers as "N not visible to you"; aggregate footers annotate.

**GR-7 (P2).** Grouping by any field with collapsible groups and per-group aggregate footers; multi-level sort; filter bar with the shared filter grammar plus a natural-language filter box (PRD 08 native AI).

**GR-8 (P1).** Real-time: edits by others appear within 2 seconds, cell-level presence indicators (avatar chip on the cell being edited), conflict rule is last-write-wins per cell with the losing writer notified inline and offered their value back. No document-level locking.

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

**GR-17 (P1).** Parent-child Blueprints render as a generated master-detail form: header fields laid out from view defaults (steward-configurable layout: sections, columns, conditional visibility), each child collection as an embedded grid beneath, with add/remove/reorder inline. Embedded child grids are the same grid component with the same budgets, trimmed by composed permissions.

**GR-18 (P2).** Grandchildren render as expandable rows within the child grid (one level of expansion in the form; deeper navigation opens the child's own detail form).

**GR-19 (P1).** The form and the grid are two renderings of the same row: opening a row from the grid slides in the detail form; edits in either surface sync live.

## Non-functional

Offline: not supported in v1; the grid degrades to read-only with a banner on connectivity loss, queuing nothing (honest failure over silent divergence). Mobile: responsive read-and-light-edit for grid and forms in v1; full mobile editing is P3. Print/export: any view exports to CSV and to the bound-Sheets snapshot (PRD 09).

## Dependencies

PRD 11 decides the rendering engine. PRD 01 supplies metadata driving renderers and layouts. PRD 05 supplies the trimmed row stream and composed child permissions. PRD 04 consumes state changes made through views.

## Open questions

1. Fill-handle formula semantics: do we support cell-anchored formulas Sheets-style, or only field-level formulas (Airtable-style)? Initial position: field-level only; cell-anchored formulas reintroduce the ungoverned-sheet problem inside our own grid. Revisit only under strong user evidence.
2. Grouped-by-state board vs workflow: when a board lane is a workflow state, is drag a transition request (with approval steps possibly pending)? Position: yes, drag creates the transition attempt and the card shows pending state if the transition has gates.
3. Concurrent structural edits (two admins editing the Blueprint while users edit rows): resolution model needed; likely Blueprint edits apply on a short debounce with active-user notification.
4. Row hierarchy vs parent-child: both exist (indent hierarchy within one Blueprint, and child Blueprints). Documentation and UI must make the distinction legible; there is a real risk users pick the wrong one. Onboarding copy and steward guidance required.
