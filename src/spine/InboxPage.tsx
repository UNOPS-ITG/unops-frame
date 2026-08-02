/**
 * What is waiting on you — approvals and update requests, one list.
 *
 * AU-4a's design fact, rendered: the two are classes of ONE pending-task
 * record, which is why "what is waiting on me" is a single query and a
 * single page rather than a tab per mechanism. An approval performs its
 * transition through the one write path when decided, under the DECIDER's
 * identity — that is what a gate is. AU-15's refusal renders beside the
 * dead buttons with its reason, because a disabled control without its
 * reason is indistinguishable from a bug.
 */

import { useState } from 'react'
import { Icon } from '@/app/icons'
import type { PendingTask } from '@/fixtures/spine/contracts'
import { actingPersona, useSpineStore } from '@/fixtures/spine/store'
import { PreviewPill } from './bits'
import './spine.css'

function when(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function InboxPage({ workspaceId }: { workspaceId: string }) {
  const tasks = useSpineStore((s) => s.tasks)
  const waiting = tasks.filter((t) => t.status === 'waiting')
  const decided = tasks.filter((t) => t.status !== 'waiting')

  return (
    <div className="spine-page">
      <div className="spine-page__inner">
        <div className="spine-page__head">
          <h2 className="spine-page__title">Inbox</h2>
          <PreviewPill what="The pending-task record" />
        </div>
        <p className="spine-page__lede">
          Approvals and update requests are one kind of thing — a pending task — so everything
          waiting on you is one list, and time-in-state is one clock. Deciding an approval performs
          its transition through the same write path as every other change, under your identity.
        </p>

        {waiting.length === 0 && (
          <p className="spine-page__lede">Nothing is waiting on you. That is the good kind of empty.</p>
        )}

        {waiting.map((t) => (
          <TaskCard key={t.id} task={t} workspaceId={workspaceId} />
        ))}

        {decided.length > 0 && (
          <>
            <h3 className="spine-page__section">Decided this session</h3>
            {decided.map((t) => (
              <TaskCard key={t.id} task={t} workspaceId={workspaceId} />
            ))}
          </>
        )}
      </div>
    </div>
  )
}

function TaskCard({ task, workspaceId }: { task: PendingTask; workspaceId: string }) {
  const decideTask = useSpineStore((s) => s.decideTask)
  const answerUpdate = useSpineStore((s) => s.answerUpdate)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const me = actingPersona()
  const selfBlocked = task.kind === 'approval' && !task.allowSelfApproval && task.requestedBy === me
  const waiting = task.status === 'waiting'

  const decide = async (decision: 'approved' | 'rejected') => {
    setBusy(true)
    setError(null)
    try {
      await decideTask({ workspaceId, taskId: task.id, decision })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'The decision could not be recorded')
    } finally {
      setBusy(false)
    }
  }

  return (
    <article
      className={`task task--${task.kind} task--${waiting ? 'waiting' : 'done'}`}
      aria-label={task.title}
    >
      <div className="task__top">
        <span className={`task__kind task__kind--${task.kind}`}>
          {task.kind === 'approval' ? <Icon.Lock className="door__gate-glyph" /> : <Icon.Fields className="door__gate-glyph" />}
          {task.kind === 'approval' ? 'Approval' : 'Update request'}
        </span>
        <h3 className="task__title">{task.title}</h3>
        <span className="task__when">{when(task.requestedAt)}</span>
      </div>

      <p className="task__detail">{task.detail}</p>

      <div className="task__meta">
        <span>
          raised by <strong>{task.requestedBy}</strong>
        </span>
        <span>
          waiting on <strong>{task.waitingOn}</strong>
        </span>
      </div>

      {task.asksFor !== undefined && (
        <div className="task__asks">
          {task.asksFor.map((f) => (
            <span key={f} className="slot slot--field">
              {f}
            </span>
          ))}
        </div>
      )}

      {waiting ? (
        <div className="task__actions">
          {task.kind === 'approval' ? (
            <>
              <button
                type="button"
                className="btn btn--primary btn--sm"
                disabled={busy || selfBlocked}
                onClick={() => void decide('approved')}
              >
                <Icon.Check />
                Approve
              </button>
              <button
                type="button"
                className="btn btn--secondary btn--sm"
                disabled={busy || selfBlocked}
                onClick={() => void decide('rejected')}
              >
                Reject
              </button>
              {selfBlocked && (
                <span className="task__blocked">
                  <Icon.Lock className="door__gate-glyph" />
                  You raised this — the gate does not allow self-approval.
                </span>
              )}
            </>
          ) : (
            <button
              type="button"
              className="btn btn--secondary btn--sm"
              disabled={busy}
              onClick={() => answerUpdate(task.id)}
            >
              Mark answered
            </button>
          )}
        </div>
      ) : (
        <span className="task__decided">
          {task.status === 'approved' && 'Approved — the transition was performed under your identity.'}
          {task.status === 'rejected' && 'Rejected. The row stays where it was.'}
          {task.status === 'answered' && 'Answered.'}
        </span>
      )}

      {error !== null && (
        <span className="gform__error" role="alert">
          {error}
        </span>
      )}
    </article>
  )
}
