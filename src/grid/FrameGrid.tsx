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

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { DataEditor, GridCellKind } from '@glideapps/glide-data-grid'
import type { CellClickedEventArgs, DataEditorRef, DrawCellCallback, EditableGridCell, GridColumn, Item, Theme } from '@glideapps/glide-data-grid'
import '@glideapps/glide-data-grid/dist/index.css'

import { useGridTheme } from '../styles/useGridTheme'
import type { GridPalette } from '../styles/useGridTheme'
import { toGlideTheme } from './glideTheme'
import { toGridCell, type FrameCell } from './cells'
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
  /** The ghost "new row" affordance at the grid's bottom was activated. The
   * parent decides what creating means (the demo register opens the guided
   * dialog, because required fields and row-conditioned grants make a silent
   * empty-row create refusable for reasons the user cannot see). */
  onAppendRow?: () => void
  /**
   * The row's OPEN action (GR-23): an affordance on the hovered row's frozen
   * primary cell that opens the row as its form view — the record page. It
   * lives on the primary column so it stays reachable however far the grid
   * scrolls, and it is a distinct callback rather than a variant of
   * selection because opening a record and selecting a row are different
   * intents a grid must not conflate.
   */
  onOpenRow?: (rowId: string) => void
  /** Row index to scroll to and flash — the landing beat after a create. The
   * parent sets it when the created row arrives in the page and clears it when
   * the flash ends; the grid only performs it. */
  flashRow?: number | undefined
  onFlashDone?: () => void
  height?: number | string
  width?: number | string
}

/* ────────────────────────────────────────────────────────────────────────────
 * ROW-CREATED STORYBOARD
 *
 *    0ms   the refreshed page lands containing the new row; grid scrolls to it
 *   60ms   the whole row tints in the selection colour (one paint, no tween —
 *          Glide's highlightRegions are atomic, and a canvas opacity ramp would
 *          repaint the full grid per frame for a subliminal difference)
 *  960ms   the tint clears; the row is just a row now, which is the point —
 *          the moment says "it landed, here", then gets out of the way
 * ──────────────────────────────────────────────────────────────────────────── */
const FLASH = {
  settle: 60, //  scroll finishes before the tint appears
  hold: 900, //   long enough to find, short enough to never feel like state
}

/** Width of the Open affordance's paint-and-click zone at the right edge of
 * the primary cell (GR-23). One constant shared by draw and hit-test. */
const OPEN_ZONE = 64

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
      return 150
    default:
      return field.variant === 'long' ? 320 : 200
  }
}

/**
 * Paints Frame's three custom cell families over the resolved palette.
 *
 * · **chip** — a select option as a tinted categorical chip with a leading dot.
 *   Status is the most-scanned column in any register, and pre-attentive colour
 *   is the difference between scanning and reading.
 * · **corporate** — a teal chip (the corporate-data role colour) whose state
 *   dot carries stale (amber) and orphaned/quarantined (cherry).
 * · **withheld** — a diagonal hatch. Withheld must read as MATERIAL: an em-dash
 *   alone is indistinguishable from "no value recorded", and that distinction
 *   is the product's headline claim.
 *
 * Everything here draws with colours resolved by `useGridTheme`; a token
 * reference given to canvas fillStyle fails silently, which is the whole reason
 * the resolver exists.
 */
// eslint-disable-next-line react-refresh/only-export-components -- a pure canvas painter colocated with the one component that calls it; a separate file would split the grid's rendering in two for a lint preference
export function paintFrameCell(
  ctx: CanvasRenderingContext2D,
  rect: { x: number; y: number; width: number; height: number },
  meta: NonNullable<FrameCell['frame']>,
  palette: GridPalette,
  glide: { baseFontStyle: string; fontFamily: string },
): void {
  if (meta.kind === 'withheld') {
    ctx.save()
    ctx.beginPath()
    ctx.rect(rect.x, rect.y, rect.width, rect.height)
    ctx.clip()
    ctx.fillStyle = palette['grid-cell-restricted-bg']
    ctx.fillRect(rect.x, rect.y, rect.width, rect.height)
    ctx.strokeStyle = palette['grid-cell-restricted-hatch']
    ctx.lineWidth = 1
    // 45° lines, 7px apart, drawn edge to edge of the clipped cell.
    for (let x = rect.x - rect.height; x < rect.x + rect.width; x += 7) {
      ctx.beginPath()
      ctx.moveTo(x, rect.y + rect.height)
      ctx.lineTo(x + rect.height, rect.y)
      ctx.stroke()
    }
    ctx.restore()
    return
  }

  const isCorporate = meta.kind === 'corporate'
  const bg = isCorporate ? palette['color-corporate-bg'] : palette[`chipcat-${meta.slot}-bg`]
  const fg = isCorporate ? palette['color-corporate-text'] : palette[`chipcat-${meta.slot}-text`]

  const chipH = Math.min(22, rect.height - 8)
  const padX = 8
  const dotR = 3
  const y = rect.y + (rect.height - chipH) / 2

  ctx.save()
  ctx.beginPath()
  ctx.rect(rect.x, rect.y, rect.width, rect.height)
  ctx.clip()

  ctx.font = `500 ${glide.baseFontStyle} ${glide.fontFamily}`
  const label = meta.label
  const textW = ctx.measureText(label).width
  const dotSpace = dotR * 2 + 5
  const chipW = Math.min(rect.width - 12, textW + padX * 2 + dotSpace)
  const x = rect.x + 6

  ctx.beginPath()
  ctx.roundRect(x, y, chipW, chipH, chipH / 2)
  ctx.fillStyle = bg
  ctx.fill()

  // The dot: the option's own ink for a select chip; for a corporate chip it is
  // the STATE — teal when healthy, amber when the snapshot is stale, cherry
  // when the relation was withdrawn upstream.
  ctx.beginPath()
  ctx.arc(x + padX + dotR - 2, y + chipH / 2, dotR, 0, Math.PI * 2)
  ctx.fillStyle = isCorporate
    ? meta.state === 'orphaned' || meta.state === 'quarantined'
      ? palette['color-governance-text']
      : meta.stale
        ? palette['chipcat-2-text']
        : fg
    : fg
  ctx.fill()

  ctx.fillStyle = fg
  ctx.textBaseline = 'middle'
  const textX = x + padX + dotR * 2 + 3
  const maxTextW = chipW - padX * 2 - dotSpace + 2
  if (textW > maxTextW) {
    // Clip long labels inside the chip rather than painting past its edge.
    ctx.save()
    ctx.beginPath()
    ctx.roundRect(x, y, chipW - padX / 2, chipH, chipH / 2)
    ctx.clip()
    ctx.fillText(label, textX, y + chipH / 2 + 0.5)
    ctx.restore()
  } else {
    ctx.fillText(label, textX, y + chipH / 2 + 0.5)
  }
  ctx.restore()
}

export function FrameGrid({
  blueprint,
  page,
  onLoadMore,
  onCellEdited,
  onRowSelected,
  onOpenCell,
  onAppendRow,
  onOpenRow,
  flashRow,
  onFlashDone,
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

  const editor = useRef<DataEditorRef>(null)
  const [flashOn, setFlashOn] = useState(false)

  useEffect(() => {
    if (flashRow === undefined) return
    editor.current?.scrollTo(0, flashRow, 'vertical')
    // Every state change rides a timer — nothing synchronous in the effect
    // body, so there is no cascading render and the storyboard is the only
    // thing that decides when paint happens.
    const show = setTimeout(() => setFlashOn(true), FLASH.settle)
    const hide = setTimeout(() => {
      setFlashOn(false)
      onFlashDone?.()
    }, FLASH.settle + FLASH.hold)
    return () => {
      clearTimeout(show)
      clearTimeout(hide)
      setFlashOn(false)
    }
  }, [flashRow, onFlashDone])

  const highlightRegions = useMemo(
    () =>
      flashOn && flashRow !== undefined
        ? [
            {
              color: theme.palette['grid-row-selected'],
              range: { x: 0, y: flashRow, width: blueprint.fields.length, height: 1 },
            },
          ]
        : undefined,
    [flashOn, flashRow, theme.palette, blueprint.fields.length],
  )

  // Row hover: the documented Glide pattern — track the hovered row from
  // onItemHovered and tint it through getRowThemeOverride. A grid without row
  // hover reads as a static table; the eye needs the row it is on.
  const [hoverRow, setHoverRow] = useState<number | undefined>(undefined)

  const onItemHovered = useCallback(
    (args: { kind: string; location: Item }) => {
      setHoverRow(args.kind === 'cell' ? args.location[1] : undefined)
    },
    [],
  )

  const getRowThemeOverride = useCallback(
    (row: number): Partial<Theme> | undefined =>
      row === hoverRow ? { bgCell: theme.palette['grid-row-hover'] } : undefined,
    [hoverRow, theme.palette],
  )

  const drawCell: DrawCellCallback = useCallback(
    (args, drawContent) => {
      const meta = (args.cell as FrameCell).frame
      if (meta === undefined) {
        drawContent()
      } else {
        paintFrameCell(args.ctx, args.rect, meta, theme.palette, glideTheme)
      }

      // GR-23's Open affordance: painted over the hovered row's primary cell,
      // right-aligned, in the accent the anchor ring already resolves. Canvas
      // has no buttons; the matching hit-test lives in handleCellClicked, and
      // the two share OPEN_ZONE so paint and click can never disagree.
      if (onOpenRow !== undefined && args.col === 0 && args.row === hoverRow) {
        const { ctx, rect } = args
        const w = OPEN_ZONE - 12
        const h = Math.min(22, rect.height - 8)
        const x = rect.x + rect.width - w - 6
        const y = rect.y + (rect.height - h) / 2
        ctx.save()
        // An opaque backing over the zone first: the chip sits ON the cell,
        // not tangled through the title's tail characters.
        ctx.fillStyle = theme.palette['grid-row-hover']
        ctx.fillRect(rect.x + rect.width - OPEN_ZONE, rect.y + 1, OPEN_ZONE, rect.height - 2)
        ctx.beginPath()
        ctx.roundRect(x, y, w, h, h / 2)
        ctx.fillStyle = theme.palette['grid-row-selected']
        ctx.fill()
        ctx.strokeStyle = theme.palette['grid-cell-anchor-ring']
        ctx.lineWidth = 1
        ctx.stroke()
        ctx.fillStyle = theme.palette['grid-cell-anchor-ring']
        ctx.font = `600 ${glideTheme.baseFontStyle} ${glideTheme.fontFamily}`
        ctx.textBaseline = 'middle'
        ctx.textAlign = 'center'
        ctx.fillText('Open', x + w / 2, y + h / 2 + 0.5)
        ctx.restore()
      }
    },
    [theme.palette, glideTheme, onOpenRow, hoverRow],
  )

  /** Clicks inside the Open chip's zone on the primary cell open the record;
   * everywhere else, clicking keeps meaning selection. */
  const handleCellClicked = useCallback(
    ([col, row]: Item, event: CellClickedEventArgs) => {
      if (onOpenRow === undefined || col !== 0) return
      if (event.localEventX < event.bounds.width - OPEN_ZONE) return
      const target = rowsById.get(row)
      if (target !== undefined) {
        event.preventDefault()
        onOpenRow(target.id)
      }
    },
    [onOpenRow, rowsById],
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
        ref={editor}
        {...(highlightRegions ? { highlightRegions } : {})}
        columns={columns}
        rows={page.rows.length}
        getCellContent={getCellContent}
        onVisibleRegionChanged={onVisibleRegionChanged}
        {...(onCellEdited ? { onCellEdited: handleCellEdited } : {})}
        {...(onOpenCell ? { onCellActivated: handleCellActivated } : {})}
        {...(onRowSelected ? { onGridSelectionChange: handleGridSelectionChange } : {})}
        {...(onOpenRow ? { onCellClicked: handleCellClicked } : {})}
        headerIcons={HEADER_ICONS}
        theme={glideTheme}
        rowHeight={theme.metrics.rowHeight}
        headerHeight={theme.metrics.headerHeight}
        drawCell={drawCell}
        onItemHovered={onItemHovered}
        getRowThemeOverride={getRowThemeOverride}
        // The primary column never scrolls away. A row whose title is off
        // screen is a row with no identity — "Closed / 64,352 / 1/9/2026"
        // belongs to nobody. Row numbers give the row an address a person can
        // say out loud ("look at row 14").
        freezeColumns={1}
        rowMarkers="number"
        {...(onAppendRow
          ? {
              trailingRowOptions: { sticky: true, tint: true, hint: 'New row…' },
              onRowAppended: () => {
                onAppendRow()
              },
            }
          : {})}
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
