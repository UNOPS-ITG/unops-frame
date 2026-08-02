/**
 * FrameGrid — the boundary between Frame and the canvas grid.
 *
 * Everything Frame-specific lives on this side of it: the wire contract, the
 * brand tokens, the withheld-cell treatment, the accessibility mirror. Glide
 * sees a column list and a `getCellContent` callback and nothing else.
 *
 * That boundary is the reason Frame depends on the published `6.0.4-alpha24`
 * rather than vendoring a fork. The fork was planned when the evidence said
 * upstream had React 19 support it was not shipping; the alphas turn out to be
 * published, just tagged `beta` rather than `latest`. Owning a fork of a large
 * canvas grid is a permanent cost, and a version pin solves the actual problem.
 * If upstream stalls, replacing it is this one file plus `cells.ts` — which is
 * what a wrapper is for.
 *
 * The grid decides nothing. It renders a page the server already trimmed.
 */

import { useCallback, useMemo } from 'react'
import { DataEditor, GridCellKind } from '@glideapps/glide-data-grid'
import type { EditableGridCell, GridColumn, Item } from '@glideapps/glide-data-grid'
import '@glideapps/glide-data-grid/dist/index.css'

import { useGridTheme } from '../styles/useGridTheme'
import { toGlideTheme } from './glideTheme'
import { toGridCell } from './cells'
import type { Blueprint, BlueprintField, Row, RowPage } from './contract'

export interface FrameGridProps {
  blueprint: Blueprint
  page: RowPage
  /** Called when the window scrolls past what is loaded. The parent owns
   * fetching, because the cursor rule (advance past every document FETCHED)
   * belongs with the transport, not the renderer. */
  onLoadMore?: () => void
  onCellEdited?: (rowId: string, fieldId: string, value: unknown) => void
  /** Which row the master-detail panel is showing. Null when the selection is
   * cleared, so the parent can close the panel rather than leave a stale row
   * open beside a grid that has moved on. */
  onRowSelected?: (rowId: string | null) => void
  /**
   * A cell was opened for editing. Return true to say the parent handled it and
   * the grid's own overlay must not open.
   *
   * The corporate-reference field is why this exists: its edit is a search over
   * a warehouse dimension in the reader's own entitlements, not a text box. A
   * text box would happily store a key nobody validated.
   */
  onOpenCell?: (rowId: string, field: BlueprintField) => boolean
  height?: number | string
  width?: number | string
}

/**
 * The withheld-column header glyph.
 *
 * A padlock drawn into Glide's header icon sprite. It replaces a column *group*
 * named "Withheld", which was the first attempt and was wrong in a way only
 * visible once rendered: Glide reserves a full-width band for a group row, so
 * one marked column produced a thirty-pixel empty stripe across every other
 * column — which reads as a rendering fault rather than as a statement about
 * one field.
 */
const HEADER_ICONS = {
  // `xmlns` is required and one line is required: Glide turns this string into
  // a data URI and loads it as an image, and a standalone SVG without the
  // namespace fails to decode. The browser reports that as an unattributed
  // "source image cannot be decoded" with no hint that an icon is the subject.
  // Drawn in `bgColor`, which is not the mistake it looks like. Glide's header
  // icon convention is a coloured backdrop with a knocked-out glyph, so
  // `bgColor` is the header's TEXT colour and `fgColor` is the header's
  // BACKGROUND — see `glideTheme.ts`. Stroking with `fgColor` paints a white
  // padlock on a white header, which is invisible and looks like the icon
  // failed to load rather than like a naming surprise.
  //
  // No backdrop square: a solid dark chip beside a column name is heavier than
  // the fact deserves. An outline padlock in the header's own ink reads as part
  // of the label.
  withheld: (props: { bgColor: string }) =>
    `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20" fill="none">` +
    `<rect x="4" y="9" width="12" height="8" rx="2" stroke="${props.bgColor}" stroke-width="1.6"/>` +
    `<path d="M7 9V6.75a3 3 0 0 1 6 0V9" stroke="${props.bgColor}" stroke-width="1.6" stroke-linecap="round"/>` +
    `</svg>`,
}

/** Columns the viewer may not read at all, on any row of this page, still
 * appear — with their header marked. Hiding them would let a reader conclude
 * the field does not exist, which is a different and wrong fact. */
function columnsFor(blueprint: Blueprint, columnStubs: readonly string[]): GridColumn[] {
  const stubs = new Set(columnStubs)
  return blueprint.fields.map((field) => ({
    id: field.id,
    title: field.label,
    width: widthFor(field),
    hasMenu: field.sortable || field.filterable,
    // Marked in the header rather than only in the cells, so the fact is stated
    // once instead of repeated down a thousand rows. Spread rather than set to
    // `undefined` because the column type does not accept an explicit absence.
    ...(stubs.has(field.id) ? { icon: 'withheld' } : {}),
  }))
}

function widthFor(field: BlueprintField): number {
  switch (field.storage) {
    case 'number':
      return 120
    case 'boolean':
      return 80
    case 'timestamp':
      return 140
    default:
      return field.variant === 'long' ? 320 : 200
  }
}

export function FrameGrid({
  blueprint,
  page,
  onLoadMore,
  onCellEdited,
  onRowSelected,
  onOpenCell,
  height = '100%',
  width = '100%',
}: FrameGridProps) {
  const theme = useGridTheme()
  const glideTheme = useMemo(() => toGlideTheme(theme), [theme])
  const columns = useMemo(
    () => columnsFor(blueprint, page.columnStubs),
    [blueprint, page.columnStubs],
  )
  const stubs = useMemo(() => new Set(page.columnStubs), [page.columnStubs])
  // Resolved once per theme change, not per cell. Passing token references
  // here would silently paint every withheld cell in whatever colour was last
  // used — canvas ignores an unparseable fillStyle rather than throwing.
  const restrictedPalette = useMemo(
    () => ({
      background: theme.palette['grid-cell-restricted-bg'],
      text: theme.palette['grid-cell-restricted-text'],
    }),
    [theme.palette],
  )

  const rowsById = useMemo(() => {
    const map = new Map<number, Row>()
    page.rows.forEach((row, index) => map.set(index, row))
    return map
  }, [page.rows])

  const getCellContent = useCallback(
    ([col, row]: Item) => {
      const field = blueprint.fields[col]
      if (field === undefined) {
        return { kind: GridCellKind.Loading as const, allowOverlay: false }
      }
      return toGridCell({
        row: rowsById.get(row),
        field,
        columnIsStub: stubs.has(field.id),
        palette: restrictedPalette,
      })
    },
    [blueprint.fields, rowsById, stubs, restrictedPalette],
  )

  const onVisibleRegionChanged = useCallback(
    (range: { y: number; height: number }) => {
      // Fetch when the window reaches the last screenful, not the last row: a
      // request issued at the final row arrives after the user has already hit
      // the bottom, which reads as the register ending.
      if (page.hasMore && range.y + range.height >= page.rows.length - 20) {
        onLoadMore?.()
      }
    },
    [onLoadMore, page.hasMore, page.rows.length],
  )

  const handleCellEdited = useCallback(
    ([col, row]: Item, newValue: EditableGridCell) => {
      const field = blueprint.fields[col]
      const target = rowsById.get(row)
      if (field === undefined || target === undefined) return
      onCellEdited?.(target.id, field.id, 'data' in newValue ? newValue.data : undefined)
    },
    [blueprint.fields, rowsById, onCellEdited],
  )

  const handleCellActivated = useCallback(
    ([col, row]: Item) => {
      const field = blueprint.fields[col]
      const target = rowsById.get(row)
      if (field === undefined || target === undefined) return
      onOpenCell?.(target.id, field)
    },
    [blueprint.fields, rowsById, onOpenCell],
  )

  const handleGridSelectionChange = useCallback(
    (selection: { current?: { cell: Item } | undefined }) => {
      const cell = selection.current?.cell
      if (cell === undefined) {
        onRowSelected?.(null)
        return
      }
      const target = rowsById.get(cell[1])
      onRowSelected?.(target?.id ?? null)
    },
    [rowsById, onRowSelected],
  )

  return (
    <div style={{ height, width, position: 'relative' }}>
      <DataEditor
        columns={columns}
        rows={page.rows.length}
        getCellContent={getCellContent}
        onVisibleRegionChanged={onVisibleRegionChanged}
        {...(onCellEdited ? { onCellEdited: handleCellEdited } : {})}
        {...(onOpenCell ? { onCellActivated: handleCellActivated } : {})}
        {...(onRowSelected ? { onGridSelectionChange: handleGridSelectionChange } : {})}
        headerIcons={HEADER_ICONS}
        theme={glideTheme}
        rowHeight={theme.metrics.rowHeight}
        headerHeight={theme.metrics.headerHeight}
        smoothScrollX
        smoothScrollY
        width={width}
        height={height}
        // Glide's own accessibility layer, plus Frame's description function
        // for the withheld case — a canvas draws pixels, so without a parallel
        // DOM structure assistive technology sees nothing at all (GR-10).
        getCellsForSelection
        keybindings={{ search: true }}
      />
      <GridAnnouncer blueprint={blueprint} page={page} />
    </div>
  )
}

/**
 * The accessibility mirror and the transparency annotation, in one live region.
 *
 * PM-5 requires the withheld count to be *stated*, not merely available: a
 * reader who cannot see that 12 rows were withheld will report the visible
 * total as the truth. Putting it in an aria-live region means the same fact
 * reaches a screen reader when the page changes.
 */
function GridAnnouncer({ blueprint, page }: { blueprint: Blueprint; page: RowPage }) {
  const { annotation } = page
  const approximate = annotation.certainty === 'estimated'

  return (
    <div
      role="status"
      aria-live="polite"
      // Named, because it is no longer the only status region on the page. A
      // test — or a screen-reader user cycling regions — needs to be able to
      // ask for *this* one rather than for whichever happens to be first.
      aria-label="Register summary"
      className="visually-hidden"
    >
      {`${blueprint.name}: ${annotation.visible} rows shown` +
        (annotation.withheld > 0 ? `, ${annotation.withheld} withheld` : '') +
        (approximate ? ' (count is approximate)' : '') +
        (page.columnStubs.length > 0
          ? `. Withheld columns: ${page.columnStubs
              .map((id) => blueprint.fields.find((f) => f.id === id)?.label ?? id)
              .join(', ')}`
          : '')}
    </div>
  )
}
