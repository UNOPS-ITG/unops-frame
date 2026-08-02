/**
 * The three states every data surface has, given first-class treatment.
 *
 * They are here rather than inlined because they are the states a product gets
 * judged on and the ones that are usually an afterthought. A blank screen while
 * loading, a blank screen when empty, and a raw error string are all the same
 * screen to a user: "it is broken".
 */

import type { ReactNode } from 'react'

export function Loading({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="skeleton" role="status" aria-live="polite" aria-busy="true">
      <span className="visually-hidden">{label}…</span>
      {/* A skeleton rather than a spinner: it says "a table is coming, roughly
          this shape", which is the difference between waiting and wondering. */}
      {Array.from({ length: 8 }, (_, i) => (
        <div key={i} className="skeleton__row" style={{ opacity: 1 - i * 0.1 }} />
      ))}
    </div>
  )
}

export function Empty({
  title,
  children,
  action,
}: {
  title: string
  children: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="state">
      <h2 className="state__title">{title}</h2>
      <p className="state__body">{children}</p>
      {action}
    </div>
  )
}

export function Failed({ title, detail, onRetry }: { title: string; detail: string; onRetry?: () => void }) {
  return (
    <div className="state" role="alert">
      <h2 className="state__title">{title}</h2>
      {/* The actual message, not a euphemism. "Something went wrong" tells the
          user nothing and tells whoever they report it to even less. */}
      <p className="state__body">{detail}</p>
      {onRetry && (
        <button type="button" className="btn btn--secondary" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  )
}

/**
 * PM-5's transparency annotation, rendered.
 *
 * The withheld count is a chip rather than prose because it has to be
 * noticeable: a reader who does not register that rows were withheld reports
 * the visible total as the truth. `certainty` is shown only when it is
 * `estimated`, because "exact" is the expectation and saying it every time
 * trains people to stop reading.
 */
export function Annotation({
  visible,
  withheld,
  certainty,
}: {
  visible: number
  withheld: number
  certainty: 'exact' | 'estimated'
}) {
  return (
    <span className="annotation">
      <span>{visible.toLocaleString()} rows</span>
      {withheld > 0 && (
        <span className="annotation__withheld" title="Rows you do not have permission to see">
          {withheld.toLocaleString()} withheld
        </span>
      )}
      {certainty === 'estimated' && (
        <span className="annotation__estimate">count is approximate</span>
      )}
    </span>
  )
}
