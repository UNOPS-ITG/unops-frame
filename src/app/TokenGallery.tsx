/* A development surface, not a product one.
 *
 * Its job is to make a theme regression visible in one screen. The grid token
 * layer in particular is impossible to review as a list of hex values — the
 * question "is the zebra stripe too strong against the selected row in grey?"
 * only has an answer when they are rendered next to each other. */

import { useThemeStore, type ThemePreference } from '@/styles/theme'
import { useGridTheme } from '@/styles/useGridTheme'

const SURFACES = ['bg', 'surface', 'surface-raised', 'surface-sunken'] as const
const BORDERS = ['border', 'border-strong', 'border-subtle'] as const
const TEXTS = ['text', 'text-secondary', 'text-muted', 'text-link'] as const
const BRAND = ['brand-primary', 'brand-subtle', 'brand-secondary'] as const
const FEEDBACK = ['brand-success', 'brand-warning', 'brand-error', 'brand-info'] as const
const VIZ = ['brand-viz-1', 'brand-viz-2', 'brand-viz-3', 'brand-viz-4', 'brand-viz-5', 'brand-viz-6'] as const
const STATUSES = ['draft', 'progress', 'active', 'warning', 'danger', 'info', 'closed', 'special'] as const
const THEMES: ThemePreference[] = ['system', 'light', 'grey', 'dark']

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ marginBlockEnd: 'var(--spacing-10)' }}>
      <h2
        style={{
          fontSize: 'var(--font-size-xs)',
          fontWeight: 'var(--font-weight-semibold)',
          textTransform: 'uppercase',
          letterSpacing: 'var(--letter-spacing-wider)',
          color: 'var(--color-text-muted)',
          marginBlockEnd: 'var(--spacing-3)',
        }}
      >
        {title}
      </h2>
      {children}
    </section>
  )
}

function Swatch({ token, label }: { token: string; label?: string }) {
  return (
    <div style={{ minWidth: '9rem' }}>
      <div
        style={{
          height: 'var(--spacing-12)',
          background: `var(--color-${token})`,
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-md)',
        }}
      />
      <code
        style={{
          display: 'block',
          marginBlockStart: 'var(--spacing-1)',
          fontSize: 'var(--font-size-xs)',
          fontFamily: 'var(--font-family-mono)',
          color: 'var(--color-text-secondary)',
        }}
      >
        {label ?? token}
      </code>
    </div>
  )
}

const Row = ({ children }: { children: React.ReactNode }) => (
  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--spacing-3)' }}>{children}</div>
)

/** A static mock of the grid so the grid tokens can be judged in context. */
function GridPreview() {
  const cells = [
    { label: 'Kandahar Road Rehabilitation', state: 'normal' },
    { label: 'Coastal Resilience Programme', state: 'stripe' },
    { label: 'Health Systems Strengthening', state: 'selected' },
    { label: 'Restricted', state: 'restricted' },
    { label: 'Water Supply — Phase II', state: 'dirty' },
    { label: 'Invalid date', state: 'error' },
  ] as const

  const bg = (state: string) =>
    ({
      normal: 'transparent',
      stripe: 'var(--grid-row-stripe)',
      selected: 'var(--grid-cell-selected)',
      restricted: 'var(--grid-cell-restricted-bg)',
      dirty: 'var(--grid-cell-dirty)',
      error: 'var(--grid-cell-error-bg)',
    })[state] ?? 'transparent'

  return (
    <div
      style={{
        border: '1px solid var(--grid-border-section)',
        borderRadius: 'var(--radius-md)',
        overflow: 'hidden',
        maxWidth: 'var(--layout-sm)',
      }}
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 7rem',
          height: 'var(--grid-header-height)',
          alignItems: 'center',
          background: 'var(--grid-header-bg)',
          color: 'var(--grid-header-text)',
          fontSize: 'var(--grid-header-font-size)',
          fontWeight: 'var(--grid-header-font-weight)',
          borderBlockEnd: '1px solid var(--grid-header-border)',
          padding: `0 var(--grid-cell-padding-x)`,
        }}
      >
        <span>Project</span>
        <span className="tabular">Budget</span>
      </div>
      {cells.map((c, i) => (
        <div
          key={c.label}
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 7rem',
            height: 'var(--grid-row-height)',
            alignItems: 'center',
            padding: `0 var(--grid-cell-padding-x)`,
            fontSize: 'var(--grid-font-size)',
            background: bg(c.state),
            borderBlockEnd: '1px solid var(--grid-border-row)',
            color: c.state === 'restricted' ? 'var(--grid-cell-restricted-text)' : 'var(--color-text)',
            fontStyle: c.state === 'restricted' ? 'italic' : 'normal',
            boxShadow: c.state === 'error' ? 'inset 0 0 0 1px var(--grid-cell-error-border)' : 'none',
          }}
        >
          <span>{c.label}</span>
          <span className="tabular">{c.state === 'restricted' ? '—' : `${(i + 1) * 12480}`}</span>
        </div>
      ))}
      <div
        style={{
          padding: 'var(--spacing-2) var(--grid-cell-padding-x)',
          fontSize: 'var(--font-size-xs)',
          color: 'var(--color-text-muted)',
          background: 'var(--grid-header-bg)',
        }}
      >
        6 shown, 2 not visible to you
      </div>
    </div>
  )
}

export function TokenGallery() {
  const { preference, resolved, setPreference } = useThemeStore()
  const { palette, metrics } = useGridTheme()

  return (
    <div className="container-lg" style={{ paddingBlock: 'var(--spacing-10)' }}>
      <header style={{ marginBlockEnd: 'var(--spacing-8)' }}>
        <h1
          style={{
            fontFamily: 'var(--font-family-display)',
            fontSize: 'var(--font-size-2xl)',
            fontWeight: 'var(--font-weight-semibold)',
            margin: 0,
          }}
        >
          Design tokens
        </h1>
        <div className="chips-row" style={{ marginBlockStart: 'var(--spacing-3)' }}>
          {THEMES.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setPreference(t)}
              className={preference === t ? 'btn btn--primary btn--sm' : 'btn btn--secondary btn--sm'}
            >
              {t}
            </button>
          ))}
          <span className="ops-chip ops-chip--mono">resolved: {resolved}</span>
        </div>
      </header>

      <Section title="Surfaces">
        <Row>{SURFACES.map((t) => <Swatch key={t} token={t} />)}</Row>
      </Section>
      <Section title="Borders">
        <Row>{BORDERS.map((t) => <Swatch key={t} token={t} />)}</Row>
      </Section>
      <Section title="Text">
        <Row>{TEXTS.map((t) => <Swatch key={t} token={t} />)}</Row>
      </Section>
      <Section title="Brand">
        <Row>{BRAND.map((t) => <Swatch key={t} token={t} />)}</Row>
      </Section>
      <Section title="Feedback">
        <Row>{FEEDBACK.map((t) => <Swatch key={t} token={t} />)}</Row>
      </Section>
      <Section title="Dataviz — order is CVD-validated, do not reorder">
        <Row>{VIZ.map((t) => <Swatch key={t} token={t} />)}</Row>
      </Section>

      <Section title="Status chips">
        <div className="chips-row">
          {STATUSES.map((s) => (
            <span key={s} className="ops-chip" data-status={s}>
              {s}
            </span>
          ))}
        </div>
      </Section>

      <Section title="Buttons">
        <Row>
          <button type="button" className="btn btn--primary">Primary</button>
          <button type="button" className="btn btn--secondary">Secondary</button>
          <button type="button" className="btn btn--danger">Danger</button>
          <button type="button" className="btn btn--ghost">Ghost</button>
          <button type="button" className="btn btn--primary" disabled>Disabled</button>
        </Row>
      </Section>

      <Section title="Form controls — the select caret must be legible in every theme">
        <Row>
          <input className="ops-input" placeholder="Text input" />
          <select className="ops-select" defaultValue="">
            <option value="">Select an option</option>
            <option value="a">Option A</option>
          </select>
        </Row>
      </Section>

      <Section title="Shadows">
        <Row>
          {(['xs', 'sm', 'md', 'lg', 'xl'] as const).map((s) => (
            <div
              key={s}
              style={{
                width: 'var(--spacing-24)',
                height: 'var(--spacing-16)',
                background: 'var(--color-surface-raised)',
                borderRadius: 'var(--radius-lg)',
                boxShadow: `var(--shadow-${s})`,
                display: 'grid',
                placeItems: 'center',
                fontSize: 'var(--font-size-xs)',
                fontFamily: 'var(--font-family-mono)',
                color: 'var(--color-text-secondary)',
              }}
            >
              {s}
            </div>
          ))}
        </Row>
      </Section>

      <Section title="Grid tokens in context">
        <GridPreview />
      </Section>

      <Section title="Canvas palette — color-mix() resolved to literals for the grid renderer">
        <div
          className="scrollable"
          style={{
            maxHeight: 'var(--spacing-24)',
            border: '1px solid var(--color-border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: 'var(--spacing-2)',
            fontFamily: 'var(--font-family-mono)',
            fontSize: 'var(--font-size-xs)',
            color: 'var(--color-text-secondary)',
          }}
        >
          {Object.entries(palette).map(([k, v]) => (
            <div key={k}>
              {k}: {v}
            </div>
          ))}
          <div>rowHeight: {metrics.rowHeight}px · headerHeight: {metrics.headerHeight}px</div>
        </div>
      </Section>
    </div>
  )
}
