/**
 * A register, live against the API.
 *
 * The counterpart to `GridDemo`: same grid, real data. What it adds is the
 * three states a governed register has that a spreadsheet does not — rows
 * withheld from you, a count that may be approximate, and a save the server
 * refused — each stated rather than left for the user to infer.
 */

import { FrameGrid } from './FrameGrid'
import { useRegister } from './useRegister'

export interface RegisterViewProps {
  workspaceId: string
  blueprintId: string
}

/** A conflicting value, rendered for a human. Never `[object Object]`: the
 * winning value may be a select key, a list, or a restricted stub, and a user
 * deciding whether to reapply their edit needs to see which. */
function describe(value: unknown): string {
  if (value === null || value === undefined) return 'empty'
  if (typeof value === 'object') {
    if (Array.isArray(value)) return value.map((v) => describe(v)).join(', ')
    if ('restricted' in value) return 'a value you may not see'
    return JSON.stringify(value)
  }
  // Enumerated rather than String()'d: a field value is always one of these,
  // and anything else reaching here is a contract violation worth seeing as
  // itself rather than as "[object Object]".
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return value.toString()
  return JSON.stringify(value) ?? 'an unreadable value'
}

export function RegisterView({ workspaceId, blueprintId }: RegisterViewProps) {
  const { blueprint, page, loading, error, rejection, loadMore, editCell, dismissRejection } =
    useRegister(workspaceId, blueprintId)

  if (error !== null) {
    return (
      <div role="alert" style={{ padding: '2rem', color: 'var(--color-danger)' }}>
        <p>{error}</p>
      </div>
    )
  }
  if (loading || blueprint === null || page === null) {
    return <div style={{ padding: '2rem', color: 'var(--color-text-secondary)' }}>Loading…</div>
  }

  const { annotation } = page

  return (
    <div
      style={{ display: 'flex', flexDirection: 'column', height: '100vh', gap: '0.75rem', padding: '1rem' }}
    >
      <header style={{ display: 'flex', alignItems: 'baseline', gap: '1rem', flexWrap: 'wrap' }}>
        <h1 style={{ font: 'var(--text-heading-3)', margin: 0 }}>{blueprint.name}</h1>
        <span style={{ color: 'var(--color-text-secondary)', font: 'var(--text-body-small)' }}>
          {annotation.visible.toLocaleString()} shown
          {/* Stated, not merely available (PM-5). A reader who cannot see that
              rows were withheld reports the visible total as the truth. */}
          {annotation.withheld > 0 && ` · ${annotation.withheld.toLocaleString()} withheld`}
          {annotation.certainty === 'estimated' && ' · count is approximate'}
        </span>
        {page.plan.unsortable !== null && (
          // Surfaced rather than swallowed: "this column cannot be sorted by
          // the index" is actionable, a sort control that does nothing is not.
          <span style={{ color: 'var(--color-warning)', font: 'var(--text-body-small)' }}>
            {page.plan.unsortable}
          </span>
        )}
      </header>

      {rejection !== null && (
        <div
          role="alert"
          style={{
            padding: '0.5rem 0.75rem',
            borderRadius: 'var(--radius-md)',
            background: 'var(--color-danger-subtle)',
            color: 'var(--color-danger)',
            font: 'var(--text-body-small)',
            display: 'flex',
            gap: '0.75rem',
            alignItems: 'center',
          }}
        >
          <span>
            {rejection.message}
            {/* The value that won, so the user can decide rather than retype
                from memory. */}
            {rejection.conflictedWith !== undefined &&
              ` — it now reads "${describe(rejection.conflictedWith)}"`}
          </span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={dismissRejection}>
            Dismiss
          </button>
        </div>
      )}

      <div
        style={{
          flex: 1,
          minHeight: 0,
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-md)',
          overflow: 'hidden',
        }}
      >
        <FrameGrid
          blueprint={blueprint}
          page={page}
          onLoadMore={loadMore}
          onCellEdited={editCell}
          height="100%"
          width="100%"
        />
      </div>
    </div>
  )
}
