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
import { toGridCell, cellDescription } from './cells'
import type { Blueprint, BlueprintField, Row, RowPage } from './contract'

export interface FrameGridProps {
  blueprint: Blueprint
  page: RowPage
  /** Called when the window scrolls past what is loaded. The parent owns
   * fetching, because the cursor rule (advance past every document FETCHED)
   * belongs with the transport, not the renderer. */
  onLoadMore?: () => void
  onCellEdited?: (rowId: string, fieldId: string, value: unknown) => void
  height?: number | string
  width?: number | string
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
    ...(stubs.has(field.id) ? { group: 'Withheld' } : {}),
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

  return (
    <div style={{ height, width, position: 'relative' }}>
      <DataEditor
        columns={columns}
        rows={page.rows.length}
        getCellContent={getCellContent}
        onVisibleRegionChanged={onVisibleRegionChanged}
        {...(onCellEdited ? { onCellEdited: handleCellEdited } : {})}
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
      style={{
        position: 'absolute',
        width: 1,
        height: 1,
        overflow: 'hidden',
        clip: 'rect(0 0 0 0)',
        whiteSpace: 'nowrap',
      }}
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

export { cellDescription }
