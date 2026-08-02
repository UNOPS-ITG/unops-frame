/**
 * A harness, not a product surface.
 *
 * It exists to make three things visible and checkable before there is a
 * backend to point at: that the canvas paints in Frame's brand tokens and
 * follows a theme change, that a withheld cell reads as withheld rather than as
 * blank, and that the grid stays responsive at the row count GR-9 sets a budget
 * for. Every number and every row here is synthetic.
 */

import { useMemo, useState } from 'react'
import { useThemeStore } from '@/styles/theme'
import type { ThemePreference } from '@/styles/theme'
import { FrameGrid } from './FrameGrid'
import type { Blueprint, Row, RowPage } from './contract'

const BLUEPRINT: Blueprint = {
  id: 'risk',
  name: 'Risk register',
  version: 1,
  tier: 'team',
  titleField: 'title',
  searchableFields: ['title'],
  slotPressure: { num: '2/8', date: '1/8', txt: '1/8' },
  unassignableSorts: [],
  fields: [
    f('title', 'Risk', 'string', { sortable: true, filterable: true }),
    f('status', 'Status', 'string', {
      filterable: true,
      options: [
        { key: 'open', label: 'Open' },
        { key: 'mitigating', label: 'Mitigating' },
        { key: 'closed', label: 'Closed' },
      ],
    }),
    f('owner', 'Owner', 'string', {}),
    f('exposure', 'Exposure (USD)', 'number', { sortable: true }),
    f('likelihood', 'Likelihood', 'number', { sortable: true }),
    f('reviewed', 'Last reviewed', 'timestamp', { sortable: true }),
    f('escalated', 'Escalated', 'boolean', {}),
    f('rationale', 'Owner rationale', 'string', {
      variant: 'long',
      sensitivity: 2,
      restricted: true,
    }),
  ],
}

function f(
  id: string,
  label: string,
  storage: string,
  over: Partial<Blueprint['fields'][number]>,
): Blueprint['fields'][number] {
  return {
    id,
    label,
    type: storage,
    variant: 'single',
    storage,
    required: false,
    readOnly: false,
    setOnce: false,
    sensitivity: 0,
    restricted: false,
    indexed: false,
    sortable: false,
    filterable: false,
    options: null,
    default: null,
    helpText: null,
    ...over,
  }
}

const STATUSES = ['open', 'mitigating', 'closed']
const OWNERS = ['A. Haddad', 'M. Osei', 'L. Fernández', 'R. Nakamura', 'T. Bergström']

function makeRows(count: number): Row[] {
  const rows: Row[] = []
  for (let i = 0; i < count; i++) {
    rows.push({
      id: `r${i.toString().padStart(6, '0')}`,
      lifecycleStatus: 'active',
      fieldVersions: {},
      values: {
        title: `Risk ${i + 1}: ${['delivery', 'supplier', 'compliance', 'currency', 'safety'][i % 5]} exposure`,
        status: STATUSES[i % 3],
        owner: OWNERS[i % OWNERS.length],
        exposure: Math.round((((i * 7919) % 500000) + 1000) / 100) * 100,
        likelihood: (i % 5) + 1,
        reviewed: new Date(2026, 0, 1 + (i % 210)).toISOString(),
        escalated: i % 11 === 0,
        // Every third row is withheld, so the withheld treatment is visible
        // beside real values rather than only in a column of its own.
        rationale: i % 3 === 0 ? { restricted: true } : `Reviewed with the owner in Q${(i % 4) + 1}.`,
      },
    })
  }
  return rows
}

const THEMES: ThemePreference[] = ['light', 'grey', 'dark']

export function GridDemo() {
  const [count, setCount] = useState(1_000)
  const rows = useMemo(() => makeRows(count), [count])
  const preference = useThemeStore((s) => s.preference)
  const setPreference = useThemeStore((s) => s.setPreference)

  const page: RowPage = useMemo(
    () => ({
      rows,
      annotation: {
        visible: rows.length,
        withheld: 12,
        total: rows.length + 12,
        scope: 'page',
        certainty: count > 5_000 ? 'estimated' : 'exact',
        ceiling: count > 5_000 ? 5_000 : null,
      },
      cursor: null,
      hasMore: false,
      columnStubs: [],
      plan: {
        storeFilters: 0,
        postFiltered: false,
        scanned: rows.length,
        rounds: 1,
        scanBudgetExhausted: false,
        reasons: [],
        unsortable: null,
      },
      blueprintId: BLUEPRINT.id,
      blueprintVersion: BLUEPRINT.version,
    }),
    [rows, count],
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', gap: '0.75rem', padding: '1rem' }}>
      <header style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
        <h1 style={{ font: 'var(--text-heading-3)', margin: 0 }}>{BLUEPRINT.name}</h1>
        <span style={{ color: 'var(--color-text-secondary)', font: 'var(--text-body-small)' }}>
          {page.annotation.visible.toLocaleString()} shown · {page.annotation.withheld} withheld
          {page.annotation.certainty === 'estimated' ? ' · count is approximate' : ''}
        </span>
        <span style={{ marginInlineStart: 'auto', display: 'flex', gap: '0.5rem' }}>
          {[1_000, 10_000, 50_000].map((n) => (
            <button
              key={n}
              type="button"
              className="btn btn-secondary btn-sm"
              aria-pressed={count === n}
              onClick={() => setCount(n)}
            >
              {n.toLocaleString()} rows
            </button>
          ))}
        </span>
        {/* The canvas resolves brand tokens once per theme change. Without a
            way to change the theme, a regression that leaves the grid painting
            in stale colours is invisible — which is the specific failure this
            harness exists to catch. */}
        <span style={{ display: 'flex', gap: '0.5rem' }}>
          {THEMES.map((t) => (
            <button
              key={t}
              type="button"
              className="btn btn-secondary btn-sm"
              aria-pressed={preference === t}
              onClick={() => setPreference(t)}
            >
              {t}
            </button>
          ))}
        </span>
      </header>
      <div style={{ flex: 1, minHeight: 0, border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
        <FrameGrid blueprint={BLUEPRINT} page={page} height="100%" width="100%" />
      </div>
    </div>
  )
}
