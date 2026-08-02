/**
 * The row's history, as a human reads it.
 *
 * PM-7's typed classes on one rail: changes carry field-level diffs rendered
 * as words, a restricted field's delta says "changed" and withholds the
 * values (the audit-read path is a PM-4 consumer, and this drawer must never
 * become the channel that hands out what the grid withheld), governance
 * events name the rule that moved, and an automation's act is attributed to
 * the recipe that took it (PM-9) — "a machine did this, and here is which".
 */

import type { ActivityEntry } from '@/fixtures/spine/contracts'
import { Icon } from '@/app/icons'
import './spine.css'

function when(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function ActivityFeed({ entries }: { entries: readonly ActivityEntry[] }) {
  if (entries.length === 0) {
    return <p className="detail__hint">Nothing yet — this row has no recorded history.</p>
  }
  return (
    <div className="feed scrollable" aria-label="Row activity">
      {entries.map((e) => (
        <article key={e.id} className="feed__entry">
          <span className={`feed__dot feed__dot--${e.cls}`} aria-hidden="true" />
          <div className="feed__meta">
            <span className="feed__actor" title={e.actor}>
              {e.actor}
            </span>
            <span className={`feed__channel${e.channel === 'automation' ? ' feed__channel--automation' : ''}`}>
              {e.channel}
            </span>
            <span className="feed__when">{when(e.at)}</span>
          </div>
          <p className="feed__summary">{e.summary}</p>
          {e.deltas !== undefined && e.deltas.length > 0 && (
            <div className="feed__deltas">
              {e.deltas.map((d, i) => (
                <span key={i} className="feed__delta">
                  <span className="feed__delta-field">{d.fieldLabel}</span>
                  {d.withheld === true ? (
                    <span className="feed__withheld">
                      <Icon.Lock className="detail__glyph" />
                      changed (value withheld)
                    </span>
                  ) : (
                    <>
                      {d.before !== undefined && <span>{d.before}</span>}
                      <span className="feed__delta-arrow" aria-hidden="true">
                        →
                      </span>
                      <span>{d.after}</span>
                    </>
                  )}
                </span>
              ))}
            </div>
          )}
        </article>
      ))}
    </div>
  )
}
