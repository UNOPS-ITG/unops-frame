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
    // unparseable colour is a black rectangle.
    return palette
      ? { ...withheld, themeOverride: { bgCell: palette.background, textDark: palette.text } }
      : withheld
  }

  const editable = !field.readOnly

  if (field.storage === 'corporate_ref' && isCorporateValue(value)) {
    return corporateCell(value, editable, palette)
  }

  switch (field.storage) {
    case 'number':
      return {
        kind: GridCellKind.Number,
        data: typeof value === 'number' ? value : undefined,
        displayData: formatValue(value, field),
        allowOverlay: editable,
        readonly: !editable,
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
function corporateCell(
  value: CorporateValue,
  editable: boolean,
  palette: RestrictedPalette | undefined,
): GridCell {
  const label = value.label ?? value.key
  const orphaned = value.state === 'orphaned' || value.state === 'quarantined'
  const suffix = orphaned ? ORPHAN_MARK : value.stale ? STALE_MARK : ''

  const cell: TextCell = {
    kind: GridCellKind.Text,
    data: value.key,
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

  return orphaned && palette
    ? { ...cell, themeOverride: { bgCell: palette.background, textDark: palette.text } }
    : cell
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
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString()
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
