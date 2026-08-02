/**
 * The workspace: what you can open.
 *
 * Deliberately not a dashboard. A dashboard is a set of decisions about what
 * matters, and nothing in Frame knows that yet — a landing page full of
 * invented widgets would be the most expensive placeholder in the product. This
 * lists the registers, says what a register *is*, and gets out of the way.
 *
 * The empty state carries the product's central claim, because a new workspace
 * is exactly when someone is deciding whether to believe it: a Blueprint is
 * published and the register exists, with no deploy and no per-Blueprint code.
 */

import { useEffect, useState } from 'react'
import { ApiError, listBlueprints } from '@/api/client'
import type { Blueprint } from '@/grid/contract'
import { Empty, Failed, Loading } from '@/registers/states'
import { Icon } from './icons'
import { href } from './routes'
import './WorkspacePage.css'

export interface WorkspacePageProps {
  workspaceId: string
}

export function WorkspacePage({ workspaceId }: WorkspacePageProps) {
  const [registers, setRegisters] = useState<Blueprint[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    listBlueprints(workspaceId)
      .then((items) => {
        if (cancelled) return
        setRegisters(items)
        // Cleared on success rather than at the start of the effect: clearing
        // up front repaints the failure state away and leaves a blank screen
        // for the length of the request, so a retry looks like it did nothing.
        setError(null)
      })
      .catch((e: unknown) => {
        if (cancelled) return
        setRegisters([])
        setError(e instanceof ApiError ? e.message : 'The workspace could not be read')
      })
    return () => {
      cancelled = true
    }
  }, [workspaceId, attempt])

  if (registers === null) return <Loading label="Opening the workspace" />

  if (error !== null) {
    return (
      <Failed
        title="This workspace could not be opened"
        detail={error}
        onRetry={() => setAttempt((a) => a + 1)}
      />
    )
  }

  if (registers.length === 0) {
    return (
      <Empty title="No registers yet">
        A steward publishes a Blueprint and its register appears here — with its
        grid, its API, its import and its permissions already working. Nobody
        builds a screen for it, and nothing is deployed.
      </Empty>
    )
  }

  return (
    <div className="workspace">
      <div className="workspace__inner">
        <p className="workspace__lead">
          Each of these is a published Blueprint. The grid, the REST surface, the
          import and the permission rules all come from its metadata — there is
          no per-register code anywhere in Frame.
        </p>

        <div className="workspace__grid">
          {registers.map((register) => (
            <a key={register.id} className="register-card" href={href.register(workspaceId, register.id)}>
              <span className="register-card__icon" aria-hidden="true">
                <Icon.Table />
              </span>
              <span className="register-card__body">
                <span className="register-card__name">{register.name}</span>
                <span className="register-card__meta">
                  {register.fields.length.toLocaleString()} fields · version{' '}
                  {register.version} · {register.tier}
                </span>
                {/* Stated here rather than discovered at sort time. Index slots
                    are finite, and a column that cannot be sorted by the store
                    is a property of the Blueprint, not of the moment. */}
                {register.unassignableSorts.length > 0 && (
                  <span className="register-card__meta">
                    {register.unassignableSorts.length} field
                    {register.unassignableSorts.length === 1 ? '' : 's'} cannot be sorted
                  </span>
                )}
              </span>
              <Icon.Chevron className="register-card__chevron" />
            </a>
          ))}
        </div>
      </div>
    </div>
  )
}
