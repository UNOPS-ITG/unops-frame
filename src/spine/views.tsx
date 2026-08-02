/**
 * The morphing views: the same rows as a board, a calendar, a Gantt.
 *
 * This is the Smartsheet capability the vision names and keeps: one data
 * set, several honest renderings, switching lossless (GR-16). Every view
 * here renders the SAME trimmed page the grid renders — the annotation
 * with its withheld count stays in the toolbar above all of them, because
 * PM-5 does not stop applying when the rows become cards or bars.
 *
 * Field maps come from the spine's BP-1a draft (`viewMaps`); a view whose
 * map is unsatisfied renders the missing-field gate, never an empty
 * canvas — the vision's honesty caveat, upheld in fixtures first.
 *
 * Caps are stated, never silent: a lane shows "+N more", the Gantt names
 * how many rows it drew. Clicking anything selects the row and opens the
 * detail panel, where the workflow doors already live.
 */

import { useMemo, useState } from 'react'
import { Icon } from '@/app/icons'
import { formatValue } from '@/grid/cells'
import { isRestricted, type Blueprint, type Row } from '@/grid/contract'
import type { SpineDef } from '@/fixtures/spine/contracts'
import { stateOf } from '@/fixtures/spine/store'
import { StateChip } from './bits'
import './spine.css'

export type DataViewMode = 'table' | 'board' | 'calendar' | 'gantt'

interface ViewProps {
  blueprint: Blueprint
  spine: SpineDef
  rows: readonly Row[]
  onSelect: (rowId: string) => void
}

function rowTitle(blueprint: Blueprint, row: Row): string {
  const fieldId = blueprint.titleField ?? blueprint.fields[0]?.id ?? ''
  const field = blueprint.fields.find((f) => f.id === fieldId)
  const value = row.values[fieldId]
  if (field === undefined || isRestricted(value)) return row.id
  return formatValue(value, field) || row.id
}

function dateOf(value: unknown): Date | null {
  if (typeof value !== 'string' || value === '') return null
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? null : d
}

/** The honest gate: a view type whose field map is unsatisfied says which
 * fields are missing instead of rendering blank (vision §3). */
export function ViewGate({ view, missing }: { view: string; missing: readonly string[] }) {
  return (
    <div className="state">
      <h2 className="state__title">No {view} for this app yet</h2>
      <p className="state__body">
        A {view} needs the app to say which fields carry it: {missing.join(', ')}. That is a
        dropdown on the Blueprint, not a build — set it and this view appears for everyone.
      </p>
    </div>
  )
}

/* --- board ---------------------------------------------------------------- */

const LANE_CAP = 30

export function BoardView({ blueprint, spine, rows, onSelect }: ViewProps) {
  const laneField = spine.viewMaps?.board?.laneField ?? spine.workflow.stateField

  const lanes = useMemo(
    () =>
      spine.workflow.states.map((state) => ({
        state,
        rows: rows.filter((r) => r.values[laneField] === state.key),
      })),
    [rows, laneField, spine],
  )

  return (
    <div className="board scrollable" aria-label="Board view">
      {lanes.map(({ state, rows: laneRows }) => (
        <section key={state.key} className="board__lane" aria-label={state.label}>
          <header className="board__head">
            <StateChip state={state} />
            <span className="board__count">{laneRows.length}</span>
          </header>
          <div className="board__cards">
            {laneRows.slice(0, LANE_CAP).map((row) => (
              <BoardCard key={row.id} blueprint={blueprint} spine={spine} row={row} onSelect={onSelect} />
            ))}
            {laneRows.length > LANE_CAP && (
              <p className="board__more">
                +{laneRows.length - LANE_CAP} more — open the table to work through them
              </p>
            )}
            {laneRows.length === 0 && <p className="board__more">Nothing here.</p>}
          </div>
        </section>
      ))}
    </div>
  )
}

function BoardCard({
  blueprint,
  spine,
  row,
  onSelect,
}: {
  blueprint: Blueprint
  spine: SpineDef
  row: Row
  onSelect: (id: string) => void
}) {
  const meta = row.values[spine.card.metaField]
  const valueField = blueprint.fields.find((f) => f.id === spine.card.valueField)
  const value = row.values[spine.card.valueField]
  return (
    <button type="button" className="card" onClick={() => onSelect(row.id)}>
      <span className="card__title">{rowTitle(blueprint, row)}</span>
      <span className="card__meta">
        {typeof meta === 'string' && <span>{meta}</span>}
        {valueField !== undefined && !isRestricted(value) && (
          <span className="card__value">{formatValue(value, valueField)}</span>
        )}
      </span>
    </button>
  )
}

/* --- calendar ------------------------------------------------------------- */

export function CalendarView({ blueprint, spine, rows, onSelect }: ViewProps) {
  const dateField = spine.viewMaps?.calendar?.dateField ?? ''

  const dated = useMemo(
    () =>
      rows
        .map((row) => ({ row, date: dateOf(row.values[dateField]) }))
        .filter((x): x is { row: Row; date: Date } => x.date !== null),
    [rows, dateField],
  )

  // Land on the busiest recent month rather than an empty "today" — a
  // calendar that opens blank teaches the user the view is broken.
  const [month, setMonth] = useState(() => {
    const latest = dated.reduce<Date | null>(
      (max, x) => (max === null || x.date > max ? x.date : max),
      null,
    )
    const base = latest ?? new Date()
    return new Date(base.getFullYear(), base.getMonth(), 1)
  })

  const grid = useMemo(() => {
    const first = new Date(month.getFullYear(), month.getMonth(), 1)
    const offset = (first.getDay() + 6) % 7 // Monday-first
    const days = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate()
    const byDay = new Map<number, { row: Row; date: Date }[]>()
    for (const x of dated) {
      if (x.date.getFullYear() === month.getFullYear() && x.date.getMonth() === month.getMonth()) {
        const list = byDay.get(x.date.getDate()) ?? []
        list.push(x)
        byDay.set(x.date.getDate(), list)
      }
    }
    return { offset, days, byDay }
  }, [dated, month])

  const label = month.toLocaleString(undefined, { month: 'long', year: 'numeric' })
  const fieldLabel = blueprint.fields.find((f) => f.id === dateField)?.label ?? dateField

  return (
    <div className="cal scrollable" aria-label="Calendar view">
      <header className="cal__bar">
        <button
          type="button"
          className="btn btn--ghost btn--icon btn--sm"
          aria-label="Previous month"
          onClick={() => setMonth((m) => new Date(m.getFullYear(), m.getMonth() - 1, 1))}
        >
          <Icon.Chevron className="cal__prev" />
        </button>
        <h3 className="cal__month">{label}</h3>
        <button
          type="button"
          className="btn btn--ghost btn--icon btn--sm"
          aria-label="Next month"
          onClick={() => setMonth((m) => new Date(m.getFullYear(), m.getMonth() + 1, 1))}
        >
          <Icon.Chevron />
        </button>
        <span className="cal__field">by {fieldLabel}</span>
      </header>
      <div className="cal__grid">
        {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((d) => (
          <span key={d} className="cal__dow">
            {d}
          </span>
        ))}
        {Array.from({ length: grid.offset }, (_, i) => (
          <span key={`pad-${i}`} className="cal__day cal__day--pad" />
        ))}
        {Array.from({ length: grid.days }, (_, i) => {
          const day = i + 1
          const items = grid.byDay.get(day) ?? []
          return (
            <div key={day} className="cal__day">
              <span className="cal__num">{day}</span>
              {items.slice(0, 3).map(({ row }) => {
                const state = stateOf(spine.workflow, row.values[spine.workflow.stateField])
                const roleClass = state === null ? '' : ` cal__item--${state.role}`
                return (
                  <button
                    key={row.id}
                    type="button"
                    className={`cal__item${roleClass}`}
                    onClick={() => onSelect(row.id)}
                    title={rowTitle(blueprint, row)}
                  >
                    {rowTitle(blueprint, row)}
                  </button>
                )
              })}
              {items.length > 3 && <span className="cal__overflow">+{items.length - 3}</span>}
            </div>
          )
        })}
      </div>
    </div>
  )
}

/* --- gantt ---------------------------------------------------------------- */

const GANTT_CAP = 48
const DAY = 86_400_000

export function GanttView({ blueprint, spine, rows, onSelect }: ViewProps) {
  const map = spine.viewMaps?.gantt

  const bars = useMemo(() => {
    if (map === undefined) return []
    return rows
      .map((row) => ({
        row,
        start: dateOf(row.values[map.startField]),
        end: dateOf(row.values[map.endField]),
      }))
      .filter((x): x is { row: Row; start: Date; end: Date } => x.start !== null && x.end !== null && x.end >= x.start)
      .sort((a, b) => a.start.getTime() - b.start.getTime())
  }, [rows, map])

  const window = useMemo(() => {
    if (bars.length === 0) return null
    const min = bars[0]!.start.getTime()
    const max = bars.reduce((m, b) => Math.max(m, b.end.getTime()), 0)
    // Pad a week each side so the first and last bars do not kiss the edge.
    return { from: min - 7 * DAY, span: max - min + 14 * DAY }
  }, [bars])

  if (map === undefined) return null
  if (window === null) {
    return (
      <ViewGate
        view="Gantt"
        missing={[
          blueprint.fields.find((f) => f.id === map.startField)?.label ?? map.startField,
          blueprint.fields.find((f) => f.id === map.endField)?.label ?? map.endField,
        ]}
      />
    )
  }

  const months: { label: string; left: number }[] = []
  for (
    let d = new Date(window.from);
    d.getTime() < window.from + window.span;
    d = new Date(d.getFullYear(), d.getMonth() + 1, 1)
  ) {
    const first = new Date(d.getFullYear(), d.getMonth(), 1)
    if (first.getTime() >= window.from) {
      months.push({
        label: first.toLocaleString(undefined, { month: 'short' }),
        left: ((first.getTime() - window.from) / window.span) * 100,
      })
    }
  }

  const shown = bars.slice(0, GANTT_CAP)

  return (
    <div className="gantt scrollable" aria-label="Gantt view">
      <div className="gantt__scale">
        <span className="gantt__label" />
        <div className="gantt__months">
          {months.map((m) => (
            <span key={m.left} className="gantt__month" style={{ insetInlineStart: `${m.left}%` }}>
              {m.label}
            </span>
          ))}
        </div>
      </div>
      {shown.map(({ row, start, end }) => {
        const state = stateOf(spine.workflow, row.values[spine.workflow.stateField])
        const roleClass = state === null ? '' : ` dist__seg--${state.role}`
        const left = ((start.getTime() - window.from) / window.span) * 100
        const width = Math.max(((end.getTime() - start.getTime()) / window.span) * 100, 0.8)
        return (
          <div key={row.id} className="gantt__row">
            <button type="button" className="gantt__label gantt__open" onClick={() => onSelect(row.id)}>
              {rowTitle(blueprint, row)}
            </button>
            <div className="gantt__track">
              <button
                type="button"
                className={`gantt__bar${roleClass}`}
                style={{ insetInlineStart: `${left}%`, inlineSize: `${width}%` }}
                onClick={() => onSelect(row.id)}
                title={`${rowTitle(blueprint, row)} · ${start.toLocaleDateString()} → ${end.toLocaleDateString()}`}
              />
            </div>
          </div>
        )
      })}
      {bars.length > shown.length && (
        <p className="gantt__note">
          Drew the first {shown.length} of {bars.length} scheduled rows — filter in the table to
          narrow what the timeline shows.
        </p>
      )}
    </div>
  )
}
