/**
 * Picking a value from corporate master data (PRD 14).
 *
 * This is the surface the whole corporate-data investment exists for: an author
 * points a field at a warehouse dimension, and a user picks from it by typing a
 * name rather than by knowing a key.
 *
 * Three constraints shape it, and each is a real limit rather than a
 * preference:
 *
 * **Never a query per keystroke.** BigQuery's best-case interactive latency is
 * ~300–400ms, most of it orchestration rather than execution, and there is no
 * warehouse-side fix: results are not cached for tables under row-level
 * security, and BI Engine does not accelerate them at all. So the search is
 * debounced, and an in-flight request is aborted when the next one starts —
 * without the abort, a slow early response can land after a fast later one and
 * repaint the list with results for a prefix the user has already moved past.
 *
 * **It runs as the person using it.** The list is what *they* may see, so an
 * empty result is reported as "nothing you can see matched" rather than
 * "nothing matched". The two are different facts and only one of them is
 * actionable.
 *
 * **The key is what gets stored, the label is a convenience.** The stored value
 * is `{key, label}`; the server decides whether the label may be cached at all,
 * which on an `entitled` dimension it may not — a cached label there is a quiet
 * bypass of the warehouse policy.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, searchDimension, type LookupRow } from '@/api/client'
import { Icon } from '@/app/icons'
import './CorporatePicker.css'

/** Long enough that a typist does not fire a query per character, short enough
 * that it does not feel laggy. Below ~200ms the debounce stops doing its job. */
const DEBOUNCE_MS = 250

export interface CorporatePickerProps {
  workspaceId: string
  dimensionId: string
  dimensionLabel: string
  /** Shown while the first search has not run, so the dialog opens with the
   * current value visible rather than empty. */
  currentLabel?: string | undefined
  onPick: (row: LookupRow) => void
  onClose: () => void
}

export function CorporatePicker({
  workspaceId,
  dimensionId,
  dimensionLabel,
  currentLabel,
  onPick,
  onClose,
}: CorporatePickerProps) {
  const [term, setTerm] = useState('')
  const [rows, setRows] = useState<LookupRow[] | null>(null)
  const [truncated, setTruncated] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [active, setActive] = useState(0)

  const inFlight = useRef<AbortController | null>(null)
  const input = useRef<HTMLInputElement>(null)

  useEffect(() => {
    input.current?.focus()
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => {
      // The previous request is abandoned rather than awaited. Without this a
      // slow response for "ma" can land after a fast one for "mali" and repaint
      // the list with results for a prefix the user has already left.
      inFlight.current?.abort()
      const controller = new AbortController()
      inFlight.current = controller

      setBusy(true)
      setError(null)
      searchDimension(workspaceId, dimensionId, term, 25, controller.signal)
        .then((result) => {
          if (controller.signal.aborted) return
          setRows(result.rows)
          setTruncated(result.truncated)
          setActive(0)
        })
        .catch((e: unknown) => {
          if (controller.signal.aborted) return
          setRows([])
          setError(e instanceof ApiError ? e.message : 'The lookup could not be run')
        })
        .finally(() => {
          if (!controller.signal.aborted) setBusy(false)
        })
    }, DEBOUNCE_MS)

    return () => clearTimeout(timer)
  }, [workspaceId, dimensionId, term])

  useEffect(() => () => inFlight.current?.abort(), [])

  const onKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      const list = rows ?? []
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
      } else if (event.key === 'ArrowDown') {
        event.preventDefault()
        setActive((i) => Math.min(i + 1, list.length - 1))
      } else if (event.key === 'ArrowUp') {
        event.preventDefault()
        setActive((i) => Math.max(i - 1, 0))
      } else if (event.key === 'Enter') {
        event.preventDefault()
        const row = list[active]
        if (row) onPick(row)
      }
    },
    [rows, active, onPick, onClose],
  )

  return (
    <div
      className="picker__backdrop"
      onMouseDown={(e) => {
        // Only a click that both starts and ends on the backdrop closes it —
        // otherwise a drag-select that ends outside the input dismisses the
        // dialog and loses what was typed.
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        className="picker"
        role="dialog"
        aria-modal="true"
        aria-label={`Choose from ${dimensionLabel}`}
        onKeyDown={onKeyDown}
      >
        <div className="picker__header">
          <h2 className="picker__title">{dimensionLabel}</h2>
          <button
            type="button"
            className="btn btn--ghost btn--icon btn--sm"
            onClick={onClose}
            aria-label="Close"
            style={{ marginInlineStart: 'auto' }}
          >
            <Icon.Close />
          </button>
        </div>

        <div className="picker__search">
          <Icon.Search />
          <input
            ref={input}
            className="ops-input"
            type="search"
            value={term}
            placeholder={currentLabel ? `Currently ${currentLabel}` : 'Start typing a name…'}
            aria-label={`Search ${dimensionLabel}`}
            onChange={(e) => setTerm(e.target.value)}
          />
        </div>

        <div className="picker__results" role="listbox" aria-label="Matches">
          {rows === null && <p className="picker__message">Searching…</p>}

          {error !== null && <p className="picker__message picker__message--error">{error}</p>}

          {error === null && rows?.length === 0 && (
            // Phrased as an entitlement statement, because it is one. The
            // query ran in this person's own warehouse context, and BigQuery
            // does not report what it filtered — so Frame cannot say whether
            // there were no matches or none this person may see, and saying
            // the shorter thing would assert something it does not know.
            <p className="picker__message">
              Nothing you can see matched
              {term ? ` "${term}"` : ''}. This list is filtered by your own
              warehouse access.
            </p>
          )}

          {rows?.map((row, index) => (
            <button
              key={row.key}
              type="button"
              role="option"
              aria-selected={index === active}
              className={`picker__option${index === active ? ' picker__option--active' : ''}`}
              onMouseEnter={() => setActive(index)}
              onClick={() => onPick(row)}
            >
              <span className="picker__label">{row.label}</span>
              <span className="picker__key">{row.key}</span>
            </button>
          ))}
        </div>

        <div className="picker__footer">
          {busy && <span>Searching…</span>}
          {!busy && truncated && (
            // Said out loud. A picker that shows the first 25 of 900 matches
            // and implies that is all of them sends people away convinced the
            // thing they wanted does not exist.
            <span>Showing the first {rows?.length ?? 0} matches — keep typing to narrow.</span>
          )}
          {!busy && !truncated && rows !== null && rows.length > 0 && (
            <span>{rows.length} matches</span>
          )}
          <span className="picker__context">
            <Icon.Warehouse />
            Resolved in your own context
          </span>
        </div>
      </div>
    </div>
  )
}
