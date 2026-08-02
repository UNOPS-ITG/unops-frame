/**
 * A register: the grid, its toolbar, and everything a governed grid has that a
 * spreadsheet does not.
 *
 * Four things are stated here rather than left for a user to infer, and each is
 * a fact somebody would otherwise get wrong in a meeting:
 *
 * 1. **Rows were withheld from you.** A count that quietly excludes what you
 *    cannot see is a count people repeat as the truth.
 * 2. **The count may be approximate.** A windowed register cannot evaluate
 *    every row of the filtered set, and pretending otherwise is worse than the
 *    approximation.
 * 3. **A sort silently did nothing.** Index slots are finite; a control that
 *    accepts a click and changes no order is the least debuggable UI there is.
 * 4. **A save was refused, and what won instead.** Handing back the winning
 *    value is the difference between deciding and retyping from memory.
 */

import { useCallback, useMemo, useState } from 'react'
import { updateRow, type LookupRow } from '@/api/client'
import { Icon } from '@/app/icons'
import { CorporatePicker } from '@/corporate/CorporatePicker'
import { FrameGrid } from '@/grid/FrameGrid'
import { RegisterToolbar } from '@/grid/RegisterToolbar'
import { useRegister } from '@/grid/useRegister'
import { isCorporateValue, type BlueprintField } from '@/grid/contract'
import { NewRow } from './NewRow'
import { RowDetail } from './RowDetail'
import { Annotation, Empty, Failed, Loading } from './states'
import './RegisterPage.css'

export interface RegisterPageProps {
  workspaceId: string
  blueprintId: string
  viewId?: string | undefined
}

/** A conflicting value, rendered for a human. Never `[object Object]`: the
 * winning value may be a select key, a list, or a restricted stub, and someone
 * deciding whether to reapply their edit needs to see which. */
function describe(value: unknown): string {
  if (value === null || value === undefined) return 'empty'
  if (typeof value === 'object') {
    if (Array.isArray(value)) return value.map((v) => describe(v)).join(', ')
    if ('restricted' in value) return 'a value you may not see'
    if ('key' in value) {
      const ref = value as { key: string; label?: string | null }
      return ref.label ?? ref.key
    }
    return JSON.stringify(value)
  }
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return value.toString()
  return JSON.stringify(value) ?? 'an unreadable value'
}

/** Which corporate dimension a field points at. Declared on the field by the
 * Blueprint author; without it there is nothing to search. */
function dimensionOf(field: BlueprintField): string | null {
  return field.storage === 'corporate_ref' ? field.dimension : null
}

export function RegisterPage({ workspaceId, blueprintId, viewId }: RegisterPageProps) {
  // Bumped after an import so the whole page refetches. The row set, the
  // annotation and the withheld count all move together, and rebuilding from one
  // source is both simpler and more honest than patching three things that then
  // have to agree.
  const [generation, setGeneration] = useState(0)
  const [filter, setFilter] = useState<Record<string, unknown> | null>(null)
  const [selectedRowId, setSelectedRowId] = useState<string | null>(null)
  const [picking, setPicking] = useState<{ rowId: string; field: BlueprintField } | null>(null)
  const [pickError, setPickError] = useState<string | null>(null)
  // Opt-in rather than opened by any cell click. A panel that appears whenever
  // the selection moves takes a third of the grid away from someone who was
  // only navigating, which makes the grid worse at the thing it is for.
  const [detailOpen, setDetailOpen] = useState(false)
  const [adding, setAdding] = useState(false)

  const { blueprint, page, loading, error, rejection, loadMore, editCell, dismissRejection } =
    useRegister(workspaceId, blueprintId, {
      generation,
      filter,
      ...(viewId === undefined ? {} : { viewId }),
    })

  const selectView = useCallback(
    (next: string | undefined) => {
      globalThis.location.hash =
        next === undefined
          ? `#/w/${workspaceId}/b/${blueprintId}`
          : `#/w/${workspaceId}/b/${blueprintId}/v/${next}`
    },
    [workspaceId, blueprintId],
  )

  const onImported = useCallback(() => setGeneration((g) => g + 1), [])

  const selectedRow = useMemo(
    () => page?.rows.find((r) => r.id === selectedRowId) ?? null,
    [page, selectedRowId],
  )

  /**
   * A corporate cell was opened for editing.
   *
   * Intercepted before the grid's own overlay, because typing a key into a text
   * box would store one nobody validated — and the set being picked from is a
   * warehouse dimension of hundreds of thousands of rows in *this reader's*
   * entitlements, which is a search rather than a dropdown.
   */
  const onOpenCell = useCallback(
    (rowId: string, field: BlueprintField): boolean => {
      if (field.storage !== 'corporate_ref') return false
      if (field.readOnly) return true
      if (dimensionOf(field) === null) {
        setPickError(
          `${field.label} points at corporate data but names no dimension, so there ` +
            'is nothing to pick from. A steward sets that on the Blueprint.',
        )
        return true
      }
      setPicking({ rowId, field })
      return true
    },
    [],
  )

  const applyPick = useCallback(
    async (row: LookupRow) => {
      if (picking === null) return
      const { rowId, field } = picking
      setPicking(null)
      setPickError(null)
      try {
        // Through the same field-scoped write path as every other edit. A picker
        // that wrote by its own route would be a second write channel, and BP-4
        // has exactly one.
        await updateRow(workspaceId, blueprintId, rowId, { [field.id]: { key: row.key, label: row.label } }, null)
        setGeneration((g) => g + 1)
      } catch (e) {
        setPickError(e instanceof Error ? e.message : 'The value could not be saved')
      }
    },
    [picking, workspaceId, blueprintId],
  )

  if (error !== null) {
    return (
      <Failed
        title="This register could not be opened"
        detail={error}
        onRetry={() => setGeneration((g) => g + 1)}
      />
    )
  }

  if (loading || blueprint === null || page === null) {
    return <Loading label="Opening the register" />
  }

  const { annotation } = page
  const empty = page.rows.length === 0

  return (
    <div className="register">
      <RegisterToolbar
        workspaceId={workspaceId}
        blueprintId={blueprintId}
        blueprint={blueprint}
        activeViewId={viewId}
        onSelectView={selectView}
        onImported={onImported}
        onFilter={setFilter}
        onAddRow={() => setAdding(true)}
        annotation={
          <>
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              aria-pressed={detailOpen}
              onClick={() => setDetailOpen((o) => !o)}
            >
              <Icon.Fields />
              {detailOpen ? 'Hide details' : 'Details'}
            </button>
            <span className="register__divider" aria-hidden="true" />
            <Annotation
              visible={annotation.visible}
              withheld={annotation.withheld}
              certainty={annotation.certainty}
            />
          </>
        }
      />

      {page.plan.unsortable !== null && (
        // Surfaced rather than swallowed. "This column has no index slot, so the
        // sort was not applied" is actionable; a sort control that silently does
        // nothing is the least debuggable UI there is.
        <div className="notice notice--warning" role="status">
          <div className="notice__body">{page.plan.unsortable}</div>
        </div>
      )}

      {rejection !== null && (
        <div className="notice notice--error" role="alert">
          <div className="notice__body">
            <span className="notice__title">{rejection.message}</span>
            {/* The value that won, so the user can decide rather than retype
                from memory. */}
            {rejection.conflictedWith !== undefined &&
              ` — it now reads "${describe(rejection.conflictedWith)}"`}
          </div>
          <button type="button" className="btn btn--ghost btn--sm" onClick={dismissRejection}>
            Dismiss
          </button>
        </div>
      )}

      {pickError !== null && (
        <div className="notice notice--error" role="alert">
          <div className="notice__body">{pickError}</div>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            onClick={() => setPickError(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="register__body">
        {empty ? (
          <Empty title={filter === null ? 'No rows yet' : 'Nothing matches this filter'}>
            {filter === null ? (
              <>
                This register is published and empty. Add a row, or import a CSV
                — the import shows you exactly what it will do before it does
                it.
              </>
            ) : (
              <>
                {annotation.withheld > 0
                  ? `No rows you can see match. ${annotation.withheld.toLocaleString()} matching rows were withheld from you.`
                  : 'No rows match. Try a broader filter.'}
              </>
            )}
          </Empty>
        ) : (
          <div className="register__grid">
            <FrameGrid
              blueprint={blueprint}
              page={page}
              onLoadMore={loadMore}
              onCellEdited={editCell}
              onRowSelected={setSelectedRowId}
              onOpenCell={onOpenCell}
              height="100%"
              width="100%"
            />
          </div>
        )}

        {detailOpen && (
          <RowDetail
            blueprint={blueprint}
            row={selectedRow}
            onClose={() => setDetailOpen(false)}
          />
        )}
      </div>

      {adding && (
        <NewRow
          workspaceId={workspaceId}
          blueprintId={blueprintId}
          blueprint={blueprint}
          onCreated={() => setGeneration((g) => g + 1)}
          onClose={() => setAdding(false)}
        />
      )}

      {picking !== null && (
        <CorporatePicker
          workspaceId={workspaceId}
          dimensionId={dimensionOf(picking.field) ?? ''}
          dimensionLabel={picking.field.label}
          currentLabel={currentLabelOf(page.rows, picking.rowId, picking.field.id)}
          onPick={(row) => void applyPick(row)}
          onClose={() => setPicking(null)}
        />
      )}
    </div>
  )
}

function currentLabelOf(
  rows: readonly { id: string; values: Readonly<Record<string, unknown>> }[],
  rowId: string,
  fieldId: string,
): string | undefined {
  const value = rows.find((r) => r.id === rowId)?.values[fieldId]
  return isCorporateValue(value) ? (value.label ?? value.key) : undefined
}
