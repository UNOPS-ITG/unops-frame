# PRD 11: Grid Component Evaluation

## Purpose

The vision names an explicit early decision: TanStack Table plus custom virtualization versus AG Grid licensing, and the field is wider than those two. This document surveys the credible candidates, applies Frame's requirements as the filter, and lands on a recommendation plus a structured spike protocol to confirm it. The requirements come from PRD 02: this is not a data-display grid, it is an editable, permission-trimmed, real-time, spreadsheet-feel grid that must also serve as the embedded child grid inside master-detail forms, hit 60fps at 10,000 rows, and clear WCAG 2.1 AA.

## What Frame actually needs from the component

Worth separating, because candidates blur it: the component supplies **rendering and interaction machinery** (virtualized painting, scrolling, selection, editing chrome, clipboard, keyboard). Frame supplies everything else regardless of choice: the data layer (trimmed row streams from our API), the editing semantics (validation via the single server path), cell renderers per Blueprint field type, real-time merge, the view morphing system, and restricted-stub rendering. So the question is narrower than "which grid": it is which machinery gives us Smartsheet-feel interaction fastest, without ceilings we will hit in year two, under licensing we can live with at the core of a strategic platform.

Non-negotiables derived from PRD 02: fill-down/fill-right with pattern continuation, range selection and Sheets-interoperable clipboard, per-cell custom renderers and editors, frozen columns, row hierarchy, variable row heights, embedded reuse inside forms, 60fps at 10k rows and 30 columns, screen-reader operability, and no license term that penalizes external-facing deployment (forms are external today, composed apps may be later).

## Candidates

### AG Grid Enterprise

The feature ceiling of the market: range selection, fill handle, clipboard fidelity, master/detail, row grouping, server-side row model, tree data, all first-party and battle-tested. DOM-based rendering with strong virtualization. Licensing is the friction: Enterprise runs <cite index="5-1">$999 per developer per year</cite>, licenses are <cite index="6-1">perpetual with one year of updates and support</cite>, and the license counts <cite index="5-1">every developer who works with AG Grid code, not just those actively developing it</cite>. Historically AG Grid's terms also distinguish internal use, with <cite index="8-1">customer-facing (external) applications requiring a Deployment License Add-on</cite>, which matters for our external forms and future partner-facing apps and would need contractual clarity before commitment. Raw cost is trivial at our scale (call it 6 to 8 frontend developers, roughly $6,000 to $8,000 a year, or roughly double with the deployment add-on); the real considerations are seat administration, a commercial dependency at the heart of a strategic platform, theming effort to escape its default look, and a community bundle already around <cite index="35-1">330 KB gzipped</cite> before Enterprise modules.

Assessment: lowest risk to Phase 1 velocity, highest long-term dependency. AG Grid's fill handle, range model, and clipboard are exactly the Smartsheet-feel features that are miserable to rebuild well.

### Glide Data Grid

Canvas-based, MIT, built by Glide as the foundation of their own Airtable-class product, which makes it the only candidate whose native design center is precisely Frame's use case. <cite index="13-1">It supports millions of rows with lazy on-demand cell rendering, native scrolling, built-in editing, resizable and movable columns, variable row heights, merged cells, and multi-select of rows, cells, and columns</cite>, and the maintainers' own rationale for canvas is the one that matters for our budgets: <cite index="13-1">DOM virtualization hits a wall when hundreds of elements load and unload per frame, and nothing saves scrolling performance at that point</cite>. Custom cells are fully supported <cite index="17-1">but renderers must draw to canvas</cite>, with editors as DOM overlays. Two real concerns. First, ecosystem currency: <cite index="14-1">the published peer dependency range covers React 16.12 through 18</cite>, so React 19 compatibility must be verified against current releases during the spike (community forks and patches exist; first-party status needs checking, not assuming). Second, maintenance is anchored to one company's product needs; MIT licensing means we can vendor and fork, and our build-in-house posture makes that credible, but it is a cost we would be choosing.

Assessment: the best architectural fit and the strongest performance story, with ownership burden as the price. Canvas rendering also raises the accessibility bar we must independently verify (the project claims first-class accessibility; we audit, we do not trust marketing, ours or theirs).

### TanStack Table + TanStack Virtual (headless, build our own)

<cite index="30-1">The engine is free, but rendering, virtualization, accessibility, and testing are real effort you must plan for</cite>, and that summary undersells it for our case: the hard parts of Smartsheet-feel (fill handle mechanics, range selection edge cases, clipboard HTML flavor fidelity, IME composition in cells, screen-reader grid semantics) are not in the engine at all. TanStack gives us column/row state management at <cite index="35-1">roughly 15 KB gzipped</cite> and total control. It is also DOM-based at the end of the day, subject to the same virtualization ceiling Glide abandoned.

Assessment: right tool for our secondary tables (catalog lists, admin screens, run logs), wrong place to spend a year of our best frontend capacity rebuilding interaction machinery that two other candidates ship today. Adopt for secondary surfaces regardless of the primary decision.

### MUI X Data Grid Premium

Capable and commercial (<cite index="29-1">Pro from $180 and Premium from $588 per developer per year</cite>), but Material-coupled: <cite index="30-1">forcing it far outside Material styling often costs more than choosing a headless option</cite>, and its editing model is form-like rather than spreadsheet-like (no fill handle culture). Not our design system, not our interaction model.

### Univer

Interesting for a different question. <cite index="22-1">Apache 2.0, isomorphic, canvas-rendered, with 450+ Excel-compatible functions and a dependency-graph formula engine that can run in workers or server-side</cite>, plus OT-based collaboration. But Univer is a spreadsheet document framework: adopting it as the grid means adopting its workbook document model, which competes with the Blueprint as the source of truth, recreating inside Frame the exact ungoverned-cells problem Frame exists to end. Its formula engine is worth watching as a reference (or component) for our own formula work, and Univer would be a candidate if we ever wanted an embedded free-form spreadsheet widget, a need currently covered better by bound Sheets.

### Handsontable, Jspreadsheet, Luckysheet/Fortune-sheet, Adazzle react-data-grid

Handsontable: spreadsheet-feel but commercial (<cite index="23-1">$899 per developer with no free commercial tier</cite>, <cite index="24-1">open-source license discontinued in 2019</cite>), <cite index="23-1">no built-in real-time collaboration</cite>, DOM-based, heavier bundle. Dominated by AG Grid on features and by Glide on architecture. Jspreadsheet CE/Pro: lighter, but the free tier lacks virtual rendering and the ecosystem is small for a strategic bet. Luckysheet is effectively unmaintained; Fortune-sheet is its small-community successor; both are workbook-model tools with the same conceptual mismatch as Univer and less engineering behind them. Adazzle react-data-grid: solid MIT editable grid, but thin on range/fill/clipboard depth. All declined for the primary grid.

## Recommendation

**Primary: adopt Glide Data Grid as the rendering engine inside a Frame-owned grid component, with AG Grid Enterprise as the named fallback, decided by a three-week head-to-head spike.**

The reasoning, stated so it can be attacked: Frame's grid must feel like a product we own, morph across five view types, embed inside generated forms, render restricted stubs and annotated counts, and stay fast as Blueprints grow. Canvas rendering is the architecture that holds at our budgets, and Glide is the only mature MIT canvas grid whose design center is our product category. MIT means the dependency is vendorable: we pin, patch, and if necessary fork, which converts the maintenance risk from existential to budgeted, and matches how we already think about strategic dependencies. What Glide does not give us (fill-handle pattern logic, clipboard fidelity edge cases, a11y depth) is genuine work, which is why the spike exists and why AG Grid, which ships those exact features, stays live as the fallback rather than a strawman. If the spike shows the editing-layer gap costs more than roughly six developer-weeks to close to Smartsheet-feel, AG Grid Enterprise wins on honest economics and we negotiate the deployment-license terms before signing.

**Secondary, decided now regardless of the spike:** TanStack Table for non-canonical tables across the product; no workbook-model component (Univer, Fortune-sheet) anywhere in the canonical data path; bound Sheets remains the free-form spreadsheet surface.

## Spike protocol (3 weeks, two engineers, same harness for both candidates)

Build the identical thin vertical against a stub API in both candidates and measure:

1. **Performance harness (week 1):** 10k and 50k rows, 30 columns, mixed field types including canvas-rendered select chips and user avatars; measure scroll fps, edit-commit latency, view-switch time, cold-mount time; mid-range hardware profile; results recorded in the repo, harness kept as the permanent CI performance gate (GR-9).
2. **Interaction fidelity (week 2):** implement fill-down with date pattern continuation, range copy/paste against Google Sheets round-trip (values and basic formats), a reference-picker editor, undo/redo, and an embedded second instance inside a form layout; score against a written Smartsheet-parity checklist.
3. **Hard cases (week 3):** restricted column stubs and "N not visible" group headers; live remote edits at 10 edits/second with presence chips; variable row heights with rich text; React 19 and Vite build verification; screen-reader walkthrough (NVDA plus VoiceOver) against the WCAG checklist; bundle and memory profile.
4. **Exit report:** per-criterion scores, estimated cost-to-close for each gap, license and vendoring analysis, and a recommendation memo. Decision made in the report review, not deferred.

Success criteria are the PRD 02 budgets verbatim; any candidate missing GR-9 or GR-10 at spike end is out regardless of other scores.

## Decision owner and timing

Owner: Frame lead engineer with CIO sign-off, given the strategic weight. Timing: the spike is the first engineering activity of Phase 1; nothing else in PRD 02 starts until the engine is chosen, because everything in PRD 02 sits on it.
