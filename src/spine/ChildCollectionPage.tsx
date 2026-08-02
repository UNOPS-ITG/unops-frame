/**
 * A child collection, flat across parents (BP-8).
 *
 * "All mitigation actions, regardless of risk" is the second half of the
 * parent-child claim: children travel with their parent AND have a life of
 * their own. Each row links back to its parent's record page, because a
 * flat child row without its parent one click away is an orphan. Parents
 * are real fetched rows; the child rows are the same fixture derivation
 * the record page uses, so the two surfaces always agree.
 */

import { useEffect, useMemo, useState } from 'react'
import { getBlueprint, queryRows } from '@/api/client'
import { href } from '@/app/routes'
import { formatValue } from '@/grid/cells'
import { isRestricted, type Blueprint, type Row } from '@/grid/contract'
import type { ChildRow, SpineDef } from '@/fixtures/spine/contracts'
import { childRowsFor } from '@/fixtures/spine/store'
import { PreviewPill } from './bits'
import './spine.css'

const CAP = 60

export function ChildCollectionPage({
  workspaceId,
  blueprintId,
  collectionId,
  spine,
}: {
  workspaceId: string
  blueprintId: string
  collectionId: string
  spine: SpineDef
}) {
  const table = spine.childTables.find((t) => t.id === collectionId)
  const [blueprint, setBlueprint] = useState<Blueprint | null>(null)
  const [rows, setRows] = useState<readonly Row[] | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      getBlueprint(workspaceId, blueprintId),
      queryRows(workspaceId, blueprintId, { limit: 200 }),
    ])
      .then(([bp, page]) => {
        if (cancelled) return
        setBlueprint(bp)
        setRows(page.rows)
      })
      .catch(() => {
        if (!cancelled) setRows([])
      })
    return () => {
      cancelled = true
    }
  }, [workspaceId, blueprintId])

  const flat = useMemo(() => {
    if (rows === null || blueprint === null || table === undefined) return null
    const titleFieldId = blueprint.titleField ?? 'title'
    const titleField = blueprint.fields.find((f) => f.id === titleFieldId)
    const out: { parentId: string; parentTitle: string; child: ChildRow }[] = []
    for (const row of rows) {
      const tv = row.values[titleFieldId]
      const parentTitle =
        titleField !== undefined && !isRestricted(tv) ? formatValue(tv, titleField) || row.id : row.id
      for (const child of childRowsFor(spine.blueprintId, table.id, row.id, row.values)) {
        out.push({ parentId: row.id, parentTitle, child })
      }
    }
    return out
  }, [rows, blueprint, table, spine])

  if (table === undefined) {
    return (
      <div className="state">
        <h2 className="state__title">No such collection</h2>
        <p className="state__body">This app declares no child collection with that name.</p>
      </div>
    )
  }

  return (
    <div className="spine-page">
      <div className="spine-page__inner spine-page__inner--wide">
        <div className="spine-page__head">
          <h2 className="spine-page__title">{table.label}</h2>
          <PreviewPill what="Child rows" />
        </div>
        <p className="spine-page__lede">
          Every {table.label.toLowerCase().replace(/s$/, '')} across all{' '}
          {spine.entityLabel.toLowerCase()}, flat — children travel with their parent, and still
          have a life of their own. Each row links back to the record it belongs to.
        </p>

        {flat === null ? (
          <p className="panel__empty">Loading…</p>
        ) : (
          (() => {
            const rest = table.columns.slice(1)
            const template = `2.2fr 1.4fr ${rest.map(() => '1fr').join(' ')}`
            return (
          <div className="rtable rtable--page">
            <div className="rtable__head" style={{ gridTemplateColumns: template }}>
              <span>{table.columns[0]?.label ?? 'Item'}</span>
              <span>Belongs to</span>
              {rest.map((c) => (
                <span key={c.id}>{c.label}</span>
              ))}
            </div>
            {flat.slice(0, CAP).map(({ parentId, parentTitle, child }, i) => (
              <div key={i} className="rtable__row" style={{ gridTemplateColumns: template }}>
                <span>{child.values[table.columns[0]?.id ?? ''] ?? ''}</span>
                <span>
                  <a className="rtable__parent" href={href.record(workspaceId, blueprintId, parentId)}>
                    {parentTitle}
                  </a>
                </span>
                {rest.map((c) =>
                  c.id === 'state' ? (
                    <span key={c.id}>
                      {child.stateLabel !== undefined && (
                        <span className={`state-chip state-chip--${child.stateRole ?? 'draft'}`}>
                          {child.stateLabel}
                        </span>
                      )}
                    </span>
                  ) : (
                    <span key={c.id}>{child.values[c.id] ?? ''}</span>
                  ),
                )}
              </div>
            ))}
            {flat.length > CAP && (
              <p className="gantt__note">
                Showing the first {CAP} of {flat.length.toLocaleString()} — the served collection
                gets the same filters and views as any table.
              </p>
            )}
          </div>
            )
          })()
        )}
      </div>
    </div>
  )
}
