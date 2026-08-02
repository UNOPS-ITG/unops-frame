/**
 * The row's place in its workflow, and the doorways out of it.
 *
 * Transitions are ACTIONS, not cell edits (AU-10) — which is why the state
 * cell in the grid opens this panel instead of a text overlay. A doorway
 * states its destination, names its gate where one stands (AU-4), and a
 * doorway the row does not qualify for is shown shut WITH its reason rather
 * than hidden: a control that vanishes teaches nobody what the rule is.
 *
 * The availability answer comes from the fixture layer, which is playing
 * the server (AU-10 gates evaluate only data Frame holds). The component
 * renders a decision; it never makes one — the same rule as the grid.
 */

import { useState } from 'react'
import { Icon } from '@/app/icons'
import type { Row } from '@/grid/contract'
import type { SpineDef, TransitionDef } from '@/fixtures/spine/contracts'
import { stateOf, transitionsFrom, useSpineStore } from '@/fixtures/spine/store'
import { PreviewPill, StateChip } from './bits'
import './spine.css'

/**
 * The fixture playing the server: evaluates a transition's condition against
 * the row. Understands exactly the shape the demo workflow uses; the real
 * evaluator is the shared grammar (`functions/lib/grammar/`), and this
 * function is deleted with the fixtures.
 */
function availability(t: TransitionDef, row: Row): { open: boolean; why: string | null } {
  if (t.condition === undefined) return { open: true, why: null }
  const match = /^(\w+) < (\d+)$/.exec(t.condition.expression)
  if (match === null) return { open: true, why: null }
  const value = row.values[match[1] as string]
  const open = typeof value === 'number' && value < Number(match[2])
  return { open, why: open ? null : t.condition.explains }
}

export function WorkflowPanel({
  workspaceId,
  spine,
  row,
  rowTitle,
}: {
  workspaceId: string
  spine: SpineDef
  row: Row
  rowTitle: string
}) {
  const performTransition = useSpineStore((s) => s.performTransition)
  const requestTransition = useSpineStore((s) => s.requestTransition)
  const [notice, setNotice] = useState<{ text: string; error: boolean } | null>(null)
  const [busy, setBusy] = useState(false)

  const { workflow } = spine
  const current = stateOf(workflow, row.values[workflow.stateField])
  if (current === null) return null

  const doors = transitionsFrom(workflow, current.key)

  const take = async (t: TransitionDef) => {
    setNotice(null)
    if (t.gate !== undefined) {
      requestTransition({
        blueprintId: spine.blueprintId,
        rowId: row.id,
        rowTitle,
        stateField: workflow.stateField,
        transition: t,
      })
      setNotice({
        text: `Approval requested — "${t.label}" is waiting on ${t.gate.approvers}. It appears in the inbox.`,
        error: false,
      })
      return
    }
    setBusy(true)
    try {
      await performTransition({
        workspaceId,
        blueprintId: spine.blueprintId,
        rowId: row.id,
        rowTitle,
        stateField: workflow.stateField,
        transition: t,
      })
    } catch (e) {
      // The server's words, verbatim. It evaluated the write; this panel
      // only relays what it decided.
      setNotice({ text: e instanceof Error ? e.message : 'The transition was refused', error: true })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="workflow" aria-label="Workflow">
      <div className="workflow__now">
        <span className="workflow__label">State</span>
        <StateChip state={current} hero />
        <span style={{ marginInlineStart: 'auto' }}>
          <PreviewPill what="The workflow engine" />
        </span>
      </div>

      {current.terminal === true || doors.length === 0 ? (
        <p className="workflow__terminal">
          A closed risk stays closed — corrections happen by reopening through the app owner,
          so the record keeps its history.
        </p>
      ) : (
        <div className="workflow__doors">
          {doors.map((t) => {
            const to = stateOf(workflow, t.to)
            const { open, why } = availability(t, row)
            return (
              <div key={t.id}>
                <button
                  type="button"
                  className="door"
                  disabled={busy || !open}
                  onClick={() => void take(t)}
                >
                  <Icon.ArrowRight className="door__arrow" />
                  <span className="door__verb">{t.label}</span>
                  {t.gate !== undefined && (
                    <span className="door__gate" title={`Decided by ${t.gate.approvers}; self-approval is not allowed.`}>
                      <Icon.Lock className="door__gate-glyph" />
                      {t.gate.approvers}
                    </span>
                  )}
                  {to !== null && <StateChip state={to} />}
                </button>
                {why !== null && <p className="door__why">{why}</p>}
              </div>
            )
          })}
        </div>
      )}

      {notice !== null && (
        <p className={`workflow__notice${notice.error ? ' workflow__notice--error' : ''}`} role="status">
          {notice.text}
        </p>
      )}
    </section>
  )
}
