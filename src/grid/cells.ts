/**
 * Turning a trimmed row into grid cells.
 *
 * This module renders what arrived. It evaluates no rules and consults no
 * grants — the server decided, and a second implementation here would be the
 * one that drifts. The architectural fitness suite enforces that by banning
 * decision-shaped identifiers in the client entirely.
 *
 * The load-bearing case is the restricted stub. Three properties, each of which
 * costs a real bug if missed:
 *
 * 1. It renders as **visibly withheld**, not as blank. A blank cell reads as
 *    "no value recorded", which is a different and wrong fact — and the one a
 *    user will repeat in a meeting.
 * 2. It is **never editable**. A restricted cell that accepts a keystroke sends
 *    a value for a field the writer cannot write; the server refuses it, but
 *    the user has already typed and lost their work.
 * 3. It **never copies**. A restricted value the user cannot see must not reach
 *    the clipboard as a placeholder that a paste elsewhere turns into data.
 */

import { GridCellKind } from '@glideapps/glide-data-grid'
import type { GridCell, TextCell } from '@glideapps/glide-data-grid'
import type { BlueprintField, CorporateValue, FieldValue, Row } from './contract'
import { isCorporateValue, isRestricted } from './contract'

/**
 * The custom-draw tag riding on a cell.
 *
 * Frame draws three cell families itself — select-option chips, corporate
 * reference chips, and the withheld hatch — because they are the product's
 * visual vocabulary and a plain text run cannot carry them. The tag travels ON
 * the GridCell (Glide passes the object through untouched) and `FrameGrid`'s
 * drawCell reads it; `displayData`/`copyData` still carry the plain text, so
 * the accessibility mirror, search and the clipboard are unaffected by how the
 * pixels are painted.
 */
export type FrameCellMeta =
  | { kind: 'chip'; slot: 1 | 2 | 3 | 4 | 5 | 6; label: string }
  | { kind: 'corporate'; label: string; state: 'snapshot' | 'resolved' | 'quarantined' | 'orphaned'; stale: boolean }
  | { kind: 'withheld' }

export type FrameCell = GridCell & { frame?: FrameCellMeta }

/**
 * Which chip slot a select option paints in.
 *
 * By declared index, not by hash: within one field the options must be
 * DISTINCT, and six slots hashed over three options collide often enough to
 * make two statuses the same colour — which reads as a data error. Index
 * assignment is stable for a given Blueprint version, and an option not found
 * in the declaration (retired, or free text) falls back to a hash so it still
 * gets a stable colour rather than throwing away the treatment.
 */
export function chipSlot(value: string, field: BlueprintField): 1 | 2 | 3 | 4 | 5 | 6 {
  const index = field.options?.findIndex((o) => o.key === value) ?? -1
  if (index >= 0) return ((index % 6) + 1) as 1 | 2 | 3 | 4 | 5 | 6
  let hash = 5381
  for (let i = 0; i < value.length; i += 1) hash = (hash * 33) ^ value.charCodeAt(i)
  return (((hash >>> 0) % 6) + 1) as 1 | 2 | 3 | 4 | 5 | 6
}

/** What a withheld cell shows. Not an empty string, and not a lock glyph
 * alone — screen readers get the words, sighted users get the styling. */
export const WITHHELD_TEXT = '—'
export const WITHHELD_LABEL = 'Withheld'

export interface CellContext {
  readonly row: Row | undefined
  readonly field: BlueprintField
  /** Withheld on every row of the page. Passed in so the header can render the
   * whole column as restricted rather than each cell announcing it separately. */
  readonly columnIsStub: boolean
  /**
   * RESOLVED colours, never token references.
   *
   * Glide passes a theme override straight to canvas `fillStyle`, and canvas
   * cannot resolve `var(--token)`. Worse, an unparseable `fillStyle` is
   * *silently ignored* — the previous colour stays, so a withheld cell paints
   * whatever was drawn before it. In practice that renders as a solid black
   * bar: the value is hidden, which looks like success, and the cell is
   * unreadable, which is not. `useGridTheme` exists to resolve these.
   */
  readonly palette?: RestrictedPalette
}

export interface RestrictedPalette {
  readonly background: string
  readonly text: string
}

export function toGridCell({ row, field, palette }: CellContext): GridCell {
  if (row === undefined) {
    // A row the window has not loaded yet. Distinct from an empty row: the grid
    // must show a skeleton rather than the absence of data, or scrolling looks
    // like deletion.
    return { kind: GridCellKind.Loading, allowOverlay: false }
  }

  const value = row.values[field.id]

  if (isRestricted(value)) {
    const withheld: TextCell = {
      kind: GridCellKind.Text,
      data: '',
      displayData: WITHHELD_TEXT,
      // Both false, and both deliberately. Overlay would open an editor for a
      // value the writer cannot write; copy would put a placeholder on the
      // clipboard that a paste elsewhere turns into real data.
      allowOverlay: false,
      readonly: true,
      copyData: '',
    }
    // No palette means the default theme rather than a broken override:
    // degrading to the normal cell colours is legible, degrading to an
    // unparseable colour is a black rectangle. The `frame` tag adds the
    // diagonal hatch on top — withheld must read as MATERIAL, because an
    // em-dash alone is indistinguishable from "no value recorded" at a
    // glance, and that distinction is the product's headline claim.
    const tagged: FrameCell = palette
      ? { ...withheld, themeOverride: { bgCell: palette.background, textDark: palette.text } }
      : withheld
    return { ...tagged, frame: { kind: 'withheld' } } as GridCell
  }

  const editable = !field.readOnly

  if (field.storage === 'corporate_ref' && isCorporateValue(value)) {
    return corporateCell(value, editable)
  }

  // A single-select value paints as a categorical chip: status is the
  // most-scanned column in any register, and pre-attentive colour is the
  // difference between scanning and reading. The chip slot comes from the
  // option's declared index, so a register's statuses are distinct by
  // construction.
  if (field.options && typeof value === 'string' && value !== '' && !Array.isArray(value)) {
    const label = labelFor(value, field)
    const cell: TextCell = {
      kind: GridCellKind.Text,
      data: label,
      displayData: label,
      allowOverlay: editable,
      readonly: !editable,
      copyData: label,
    }
    return { ...cell, frame: { kind: 'chip', slot: chipSlot(value, field), label } } as GridCell
  }

  switch (field.storage) {
    case 'number':
      return {
        kind: GridCellKind.Number,
        data: typeof value === 'number' ? value : undefined,
        displayData: formatValue(value, field),
        allowOverlay: editable,
        readonly: !editable,
        // Right-aligned, always. Left-aligned numerals cannot be compared down
        // a column, which is the only reason a register HAS a number column.
        contentAlign: 'right',
      }

    case 'boolean':
      return {
        kind: GridCellKind.Boolean,
        data: value === true,
        allowOverlay: false,
        readonly: !editable,
      }

    case 'string_array':
      return {
        kind: GridCellKind.Bubble,
        data: Array.isArray(value) ? value.map((v) => labelFor(String(v), field)) : [],
        allowOverlay: editable,
      }

    default: {
      // Through `formatValue` rather than `String()`. A value can legitimately
      // be an object here — a corporate reference on a field whose storage was
      // changed, say — and `String()` would put "[object Object]" into the
      // cell's edit buffer, which is then what a save writes back.
      const text = formatValue(value, field)
      return {
        kind: GridCellKind.Text,
        data: text,
        displayData: text,
        allowOverlay: editable,
        readonly: !editable,
        // Dates are comparable values, and comparable values right-align so
        // the column scans as a column rather than a ragged margin.
        ...(field.storage === 'timestamp' ? { contentAlign: 'right' as const } : {}),
      }
    }
  }
}

export const STALE_MARK = ' ·'
export const ORPHAN_MARK = ' ⚠'

/**
 * A reference to corporate data.
 *
 * Four states, and showing them identically would lose the only information
 * that distinguishes a fact from a guess:
 *
 * - **snapshot** — a cached label from an `open` dimension. Shown plainly.
 * - **snapshot, stale** — the same, but taken more than 90 days ago and marked.
 *   A silently old label is worse than a visibly old one: the first time anyone
 *   notices otherwise is when two reports disagree.
 * - **resolved** — an `entitled` dimension, resolved live in *this* reader's
 *   context. Nothing is cached; the value is theirs.
 * - **quarantined / orphaned** — the relation went away upstream. The stored
 *   key is still shown, marked, because hiding it would make the row look empty
 *   rather than orphaned, and those call for different actions.
 *
 * Never editable inline. Picking a corporate value means searching a catalogue
 * of hundreds of thousands of rows in the user's own entitlements; a text box
 * that accepted a typed key would store one nobody validated.
 */
function corporateCell(value: CorporateValue, editable: boolean): GridCell {
  const label = value.label ?? value.key
  const orphaned = value.state === 'orphaned' || value.state === 'quarantined'
  const suffix = orphaned ? ORPHAN_MARK : value.stale ? STALE_MARK : ''

  const cell: TextCell = {
    kind: GridCellKind.Text,
    data: value.key,
    // The marks stay in displayData for the accessibility mirror and search;
    // the painted chip carries the same facts as a state dot instead.
    displayData: `${label}${suffix}`,
    // No overlay, ever — not even a read-only one. Activating the cell raises
    // `onCellActivated`, and the register opens the picker in response. A text
    // overlay here would let someone type a key straight into the row, and a
    // typed key is one nobody validated against a dimension that has hundreds
    // of thousands of them.
    allowOverlay: false,
    readonly: !editable,
    copyData: value.key,
  }

  return {
    ...cell,
    frame: {
      kind: 'corporate',
      label,
      state: value.state ?? 'snapshot',
      stale: value.stale === true,
    },
  } as GridCell
}

/**
 * The option's label, never its key.
 *
 * A select field stores a stable key so renaming a label does not rewrite every
 * row (BP-12), which means the key is an internal identifier the user never
 * chose and should never be shown. Falling back to the key when no option
 * matches is deliberate: a value orphaned by an option being retired must stay
 * visible, because silently blanking it loses data the user can still see in
 * the audit trail.
 */
export function labelFor(value: string, field: BlueprintField): string {
  const option = field.options?.find((o) => o.key === value)
  return option?.label ?? value
}

export function formatValue(value: FieldValue, field: BlueprintField): string {
  if (value == null) return ''
  if (isRestricted(value)) return WITHHELD_TEXT
  if (isCorporateValue(value)) return value.label ?? value.key
  if (Array.isArray(value)) return value.map((v) => labelFor(String(v), field)).join(', ')

  if (field.options && typeof value === 'string') return labelFor(value, field)

  if (field.storage === 'timestamp' && typeof value === 'string') {
    const parsed = new Date(value)
    // An unparseable date is shown as stored rather than as "Invalid Date":
    // the raw string is at least a clue about what went wrong upstream.
    //
    // dateStyle 'medium' names the month ("2 Jan 2026" / "Jan 2, 2026"), so
    // the value is unambiguous in every locale. The previous all-numeric form
    // produced "1/2/2026", which in an international organization is genuinely
    // two different dates depending on who is reading.
    return Number.isNaN(parsed.getTime())
      ? value
      : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(parsed)
  }

  if (typeof value === 'number') return new Intl.NumberFormat().format(value)
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  return String(value)
}

/**
 * The accessible text for one cell (GR-10).
 *
 * A canvas grid draws pixels, so assistive technology sees nothing at all
 * unless a parallel DOM structure carries the same content. This is the
 * function that structure is built from, which is why the withheld case says
 * the word rather than reading out an em-dash.
 */
export function cellDescription({ row, field }: CellContext): string {
  if (row === undefined) return 'Loading'
  const value = row.values[field.id]
  if (isRestricted(value)) return WITHHELD_LABEL
  const formatted = formatValue(value, field)
  return formatted === '' ? 'Empty' : formatted
}
