/**
 * The workspace: a launcher, not an apology.
 *
 * This is the first screen anyone sees, and the previous version greeted them
 * with a sentence of architecture ("there is no per-register code anywhere in
 * Frame") and one small card adrift in white. Nobody choosing between Frame
 * and the spreadsheet they already have open cares about the architecture —
 * they care whether this looks like a place their work wants to live.
 *
 * So: a greeting-scale headline, register cards with real presence, and a
 * dashed "New register" affordance that states the promise even though the
 * authoring flow is not built yet. The architecture stays — as one quiet line
 * under the headline, where the curious can find it and nobody trips on it.
 */

import { useEffect, useState } from 'react'
import { ApiError, listBlueprints } from '@/api/client'
import { useSpineStore } from '@/fixtures/spine/store'
import type { Blueprint } from '@/grid/contract'
import { Empty, Failed, Loading } from '@/registers/states'
import { NewAppWizard } from '@/spine/NewAppWizard'
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
  const [creating, setCreating] = useState(false)
  const createdApps = useSpineStore((s) => s.createdApps)

  useEffect(() => {
    let cancelled = false
    listBlueprints(workspaceId)
      .then((items) => {
        if (cancelled) return
        setRegisters(items)
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

  if (registers.length === 0 && Object.keys(createdApps).length === 0) {
    return (
      <Empty title="No apps yet">
        Describe what you track and Frame drafts the app — model, states,
        automations — for you to review before it exists. No ticket, no deploy.
      </Empty>
    )
  }

  return (
    <div className="workspace">
      <div className="workspace__inner">
        <header className="workspace__hero">
          <h2 className="workspace__headline">Your apps</h2>
          <p className="workspace__lead">
            Everything here is governed: who sees which rows and fields is
            decided per person, and every view says what it is not showing.
          </p>
        </header>

        <div className="workspace__grid">
          {registers.map((register) => (
            <a
              key={register.id}
              className="register-card"
              href={href.register(workspaceId, register.id)}
            >
              <span className="register-card__icon" aria-hidden="true">
                <Icon.Table />
              </span>
              <span className="register-card__body">
                <span className="register-card__name">{register.name}</span>
                <span className="register-card__meta">
                  {register.fields.length.toLocaleString()} fields · v{register.version}
                  <span className="register-card__tier">{register.tier}</span>
                </span>
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

          {Object.values(createdApps).map((app) => (
            <a key={app.id} className="register-card" href={href.register(workspaceId, app.id)}>
              <span className="register-card__icon" aria-hidden="true">
                <Icon.Bolt />
              </span>
              <span className="register-card__body">
                <span className="register-card__name">{app.draft.name}</span>
                <span className="register-card__meta">
                  {app.draft.fields.length.toLocaleString()} fields · created this session
                </span>
              </span>
              <Icon.Chevron className="register-card__chevron" />
            </a>
          ))}

          <button
            type="button"
            className="register-card register-card--new"
            onClick={() => setCreating(true)}
          >
            <span className="register-card__icon register-card__icon--new" aria-hidden="true">
              <Icon.Plus />
            </span>
            <span className="register-card__body">
              <span className="register-card__name">New app</span>
              <span className="register-card__meta">
                Describe it, or adopt one the organization already runs
              </span>
            </span>
          </button>
        </div>

        <p className="workspace__footnote">
          Each app is generated from its model — the views, the REST API, the import rules
          and the permissions. Nobody builds a screen for one, ever.
        </p>
      </div>

      {creating && <NewAppWizard workspaceId={workspaceId} onClose={() => setCreating(false)} />}
    </div>
  )
}
