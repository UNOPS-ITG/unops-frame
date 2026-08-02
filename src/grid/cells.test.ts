import { describe, expect, it } from 'vitest'
import { GridCellKind } from '@glideapps/glide-data-grid'
import { cellDescription, formatValue, labelFor, toGridCell, WITHHELD_LABEL } from './cells'
import type { BlueprintField, Row } from './contract'
import { isRestricted } from './contract'

const field = (over: Partial<BlueprintField> = {}): BlueprintField => ({
  id: 'title',
  label: 'Title',
  type: 'text',
  variant: 'single',
  storage: 'string',
  required: false,
  readOnly: false,
  setOnce: false,
  sensitivity: 0,
  restricted: false,
  indexed: false,
  sortable: false,
  filterable: false,
  options: null,
  default: null,
  helpText: null,
  ...over,
})

const row = (values: Record<string, unknown>): Row => ({
  id: 'r1',
  values: values as Row['values'],
  fieldVersions: {},
  lifecycleStatus: 'draft',
})

const cell = (values: Record<string, unknown>, f: BlueprintField, stub = false) =>
  toGridCell({ row: row(values), field: f, columnIsStub: stub })

describe('the withheld cell', () => {
  it('is never editable', () => {
    // A restricted cell that accepts a keystroke sends a value for a field the
    // writer cannot write. The server refuses it — after the user has typed.
    const c = cell({ title: { restricted: true } }, field())
    expect(c.allowOverlay).toBe(false)
    expect('readonly' in c && c.readonly).toBe(true)
  })

  it('never copies a placeholder to the clipboard', () => {
    // A paste elsewhere would turn the placeholder into real data.
    const c = cell({ title: { restricted: true } }, field())
    expect('copyData' in c && c.copyData).toBe('')
  })

  it('reads as withheld rather than empty', () => {
    // "No value recorded" is a different and wrong fact — and the one a user
    // repeats in a meeting.
    expect(
      cellDescription({ row: row({ title: { restricted: true } }), field: field(), columnIsStub: false }),
    ).toBe(WITHHELD_LABEL)
    expect(
      cellDescription({ row: row({ title: '' }), field: field(), columnIsStub: false }),
    ).toBe('Empty')
  })

  it('never hands the canvas a colour it cannot parse', () => {
    // Canvas silently IGNORES an unparseable fillStyle — it does not throw, it
    // keeps the previous colour. A `var(--token)` override therefore paints
    // withheld cells in whatever was drawn before them, which reads as a solid
    // bar: the value is hidden, so it looks like it worked, and the cell is
    // unreadable, so it did not. This is the same failure `toCanvasColour`
    // exists to prevent on the theme path.
    const c = toGridCell({
      row: row({ title: { restricted: true } }),
      field: field(),
      columnIsStub: false,
      palette: { background: 'rgba(0, 0, 0, 0.06)', text: 'rgb(100, 116, 139)' },
    })
    const override = 'themeOverride' in c ? c.themeOverride : undefined
    for (const value of Object.values(override ?? {})) {
      expect(String(value), 'canvas cannot resolve a CSS custom property').not.toContain('var(')
    }
    expect(override?.bgCell).toBe('rgba(0, 0, 0, 0.06)')
  })

  it('falls back to the default theme rather than a broken override', () => {
    // Degrading to the normal cell colours is legible. Degrading to an
    // unparseable colour is a black rectangle.
    const c = cell({ title: { restricted: true } }, field())
    expect('themeOverride' in c ? c.themeOverride : undefined).toBeUndefined()
  })

  it('is withheld regardless of the field type it stands in for', () => {
    // A number cell that fell through to a numeric branch would render the
    // stub object as NaN, and a NaN in a column gets summed.
    for (const storage of ['number', 'boolean', 'timestamp', 'string_array', 'string']) {
      const c = cell({ title: { restricted: true } }, field({ storage }))
      expect(c.kind, storage).toBe(GridCellKind.Text)
      expect(c.allowOverlay, storage).toBe(false)
    }
  })
})

describe('distinguishing absent, empty and withheld', () => {
  it('treats a missing key, a null and a stub as three different things', () => {
    const f = field()
    expect(formatValue(undefined, f)).toBe('')
    expect(formatValue(null, f)).toBe('')
    expect(isRestricted({ restricted: true })).toBe(true)
    expect(isRestricted(null)).toBe(false)
    expect(isRestricted('')).toBe(false)
  })

  it('does not treat a number zero as absent', () => {
    // The classic falsy bug: a zero amount rendering as blank reads as "not
    // recorded", which for a financial column is a materially wrong statement.
    expect(formatValue(0, field({ storage: 'number' }))).toBe('0')
    const c = cell({ title: 0 }, field({ storage: 'number' }))
    expect(c.kind).toBe(GridCellKind.Number)
    expect('data' in c && c.data).toBe(0)
  })

  it('does not treat false as absent', () => {
    expect(formatValue(false, field({ storage: 'boolean' }))).toBe('No')
  })
})

describe('select options', () => {
  const withOptions = field({
    storage: 'string',
    options: [
      { key: 'open', label: 'Open' },
      { key: 'closed', label: 'Closed' },
    ],
  })

  it('shows the label, never the stored key', () => {
    // The key is a stable internal identifier the user never chose — it exists
    // so renaming a label does not rewrite every row.
    expect(formatValue('open', withOptions)).toBe('Open')
  })

  it('keeps a value orphaned by a retired option visible', () => {
    // Blanking it would lose data the user can still see in the audit trail.
    expect(labelFor('withdrawn', withOptions)).toBe('withdrawn')
  })

  it('labels every member of a multi-select', () => {
    expect(formatValue(['open', 'closed'], withOptions)).toBe('Open, Closed')
  })
})

describe('a row the window has not loaded', () => {
  it('renders as loading, not as empty', () => {
    // Scrolling past loaded data would otherwise look like deletion.
    const c = toGridCell({ row: undefined, field: field(), columnIsStub: false })
    expect(c.kind).toBe(GridCellKind.Loading)
    expect(cellDescription({ row: undefined, field: field(), columnIsStub: false })).toBe('Loading')
  })
})

describe('read-only fields', () => {
  it('do not open an editor', () => {
    const c = cell({ title: 'x' }, field({ readOnly: true }))
    expect(c.allowOverlay).toBe(false)
  })
})

describe('dates', () => {
  it('shows an unparseable value as stored rather than as Invalid Date', () => {
    // The raw string is at least a clue about what went wrong upstream.
    expect(formatValue('not-a-date', field({ storage: 'timestamp' }))).toBe('not-a-date')
  })
})
