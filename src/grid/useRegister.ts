/**
 * The hook that binds a Blueprint, its rows and its deltas into one view.
 *
 * Three things live here rather than in the component, because each is a place
 * a plausible-looking implementation is wrong:
 *
 * **The cursor is carried, never derived.** The server returns the store
 * position of the last document it *fetched*, which is not the last row it
 * showed. A client that paged from the last visible row's id would re-read
 * every withheld document between them, forever, on a register it has partial
 * access to.
 *
 * **A delta is a signal to refetch, not a patch.** Deltas carry identifiers and
 * field names, never values — so applying one means fetching the row under this
 * user's own identity. Patching from the delta would mean trusting a payload
 * trimmed for whoever wrote the row rather than for whoever is reading it.
 *
 * **An optimistic edit is reverted on refusal, with the server's reason.** The
 * alternative — leaving the typed value on screen after a 403 — tells the user
 * they saved something they did not.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ApiError,
  pollDeltas,
  queryRows,
  getBlueprint,
  updateRow,
  type Channel,
} from '../api/client'
import type { Blueprint, Row, RowPage } from './contract'

const POLL_INTERVAL_MS = 5_000

export interface CellRejection {
  rowId: string
  fieldId: string
  message: string
  /** Set when a concurrent edit won. The UI offers the value back rather than
   * discarding what the user typed. */
  conflictedWith?: unknown
}

export interface RegisterState {
  blueprint: Blueprint | null
  page: RowPage | null
  loading: boolean
  error: string | null
  rejection: CellRejection | null
  loadMore: () => void
  editCell: (rowId: string, fieldId: string, value: unknown) => void
  dismissRejection: () => void
}

export function useRegister(
  workspaceId: string,
  blueprintId: string,
  channel: Channel = 'grid',
): RegisterState {
  /**
   * One state object keyed by the register it describes.
   *
   * Loading is *derived* from whether the loaded key matches the requested one,
   * rather than being a flag an effect sets. That is not only a lint rule: a
   * separate flag means one render exists where the previous register's rows
   * are on screen with the new register's header, and someone eventually
   * reports it as "the grid showed me another team's data".
   */
  const key = `${workspaceId}/${blueprintId}`
  const [loaded, setLoaded] = useState<{
    key: string
    blueprint: Blueprint | null
    page: RowPage | null
    error: string | null
  }>({ key: '', blueprint: null, page: null, error: null })
  const [rejection, setRejection] = useState<CellRejection | null>(null)

  const settled = loaded.key === key
  const blueprint = settled ? loaded.blueprint : null
  const page = settled ? loaded.page : null
  const error = settled ? loaded.error : null
  const loading = !settled

  // Refs rather than state: the poll loop reads these and must not be a reason
  // to re-subscribe, or every delta would tear down and rebuild the timer.
  const watermark = useRef<string | null>(null)
  const pageRef = useRef<RowPage | null>(null)
  // Synced in an effect, not during render. Writing a ref while rendering makes
  // the value depend on whether React committed that render, which under
  // concurrent rendering it may not. One poll tick of staleness costs nothing
  // here — the tick refetches anyway.
  useEffect(() => {
    pageRef.current = page
  }, [page])

  const setPage = useCallback(
    (next: RowPage | null | ((prev: RowPage | null) => RowPage | null)) => {
      setLoaded((prev) => ({
        ...prev,
        page: typeof next === 'function' ? next(prev.page) : next,
      }))
    },
    [],
  )

  useEffect(() => {
    let cancelled = false
    watermark.current = null

    Promise.all([
      getBlueprint(workspaceId, blueprintId),
      queryRows(workspaceId, blueprintId, { limit: 200 }),
    ])
      .then(([bp, first]) => {
        if (!cancelled) setLoaded({ key, blueprint: bp, page: first, error: null })
      })
      .catch((e: unknown) => {
        if (cancelled) return
        setLoaded({
          key,
          blueprint: null,
          page: null,
          error: e instanceof Error ? e.message : 'Could not load the register',
        })
      })

    return () => {
      cancelled = true
    }
  }, [workspaceId, blueprintId, key])

  const refresh = useCallback(async () => {
    // A full refetch rather than a targeted one. Refetching only the changed
    // rows would leave the annotation and the withheld count stale, and a
    // withheld count that lags is worse than no count at all — it is a wrong
    // number the reader trusts.
    const fresh = await queryRows(workspaceId, blueprintId, { limit: 200 })
    setPage(fresh)
  }, [workspaceId, blueprintId, setPage])

  // The delta loop.
  useEffect(() => {
    let stopped = false
    let timer: ReturnType<typeof setTimeout> | undefined

    const tick = async () => {
      try {
        const known = (pageRef.current?.rows ?? []).map((r) => r.id)
        const result = await pollDeltas(workspaceId, blueprintId, watermark.current, known)
        // Advanced even when the batch produced nothing, or a client whose next
        // envelopes are all invisible to it re-examines the same ones forever.
        watermark.current = result.since
        if (!stopped && result.deltas.length > 0) await refresh()
      } catch {
        // A failed poll is not a failed register. Staying quiet and retrying is
        // right; surfacing an error banner for a background refresh trains
        // users to ignore error banners.
      } finally {
        if (!stopped) timer = setTimeout(() => void tick(), POLL_INTERVAL_MS)
      }
    }

    timer = setTimeout(() => void tick(), POLL_INTERVAL_MS)
    return () => {
      stopped = true
      if (timer) clearTimeout(timer)
    }
  }, [workspaceId, blueprintId, refresh])

  const loadMore = useCallback(() => {
    const current = pageRef.current
    if (!current?.hasMore || !current.cursor) return

    queryRows(workspaceId, blueprintId, { limit: 200, cursor: current.cursor })
      .then((next) => {
        setPage((prev) =>
          prev === null
            ? next
            : {
                ...next,
                rows: [...prev.rows, ...next.rows],
                annotation: {
                  ...next.annotation,
                  // Accumulated across pages: a per-page count would tell the
                  // reader 3 rows were withheld when 300 were.
                  visible: prev.annotation.visible + next.annotation.visible,
                  withheld: prev.annotation.withheld + next.annotation.withheld,
                  total: prev.annotation.total + next.annotation.total,
                  scope: 'loaded',
                },
              },
        )
      })
      .catch((e: unknown) => {
        setLoaded((prev) => ({
          ...prev,
          error: e instanceof Error ? e.message : 'Could not load more rows',
        }))
      })
  }, [workspaceId, blueprintId, setPage])

  const editCell = useCallback(
    (rowId: string, fieldId: string, value: unknown) => {
      const current = pageRef.current
      const target = current?.rows.find((r) => r.id === rowId)
      if (current === null || current === undefined || target === undefined) return

      const previous = target.values[fieldId]
      setPage(patchRow(current, rowId, fieldId, value))

      updateRow(
        workspaceId, blueprintId, rowId,
        { [fieldId]: value },
        // Only the field being written. Sending every version the client holds
        // would make an unrelated concurrent edit look like a conflict.
        { [fieldId]: target.fieldVersions[fieldId] ?? 0 },
        channel,
      )
        .then((result) => {
          setPage((prev) => (prev ? stampVersions(prev, rowId, result.fieldVersions) : prev))
        })
        .catch((e: unknown) => {
          // Put the stored value back. Leaving the typed one on screen after a
          // refusal tells the user they saved something they did not.
          setPage((prev) => (prev ? patchRow(prev, rowId, fieldId, previous) : prev))
          if (e instanceof ApiError) {
            setRejection({
              rowId,
              fieldId,
              message: e.isConflict
                ? 'Someone else changed this cell while you were editing it'
                : (e.fieldErrors.find((f) => f.fieldId === fieldId)?.message ?? e.message),
              ...(e.isConflict ? { conflictedWith: e.currentValues[fieldId] } : {}),
            })
          } else {
            setRejection({ rowId, fieldId, message: 'The change could not be saved' })
          }
        })
    },
    [workspaceId, blueprintId, channel, setPage],
  )

  return {
    blueprint,
    page,
    loading,
    error,
    rejection,
    loadMore,
    editCell,
    dismissRejection: useCallback(() => setRejection(null), []),
  }
}

function patchRow(page: RowPage, rowId: string, fieldId: string, value: unknown): RowPage {
  return {
    ...page,
    rows: page.rows.map((r) =>
      r.id === rowId ? { ...r, values: { ...r.values, [fieldId]: value as Row['values'][string] } } : r,
    ),
  }
}

function stampVersions(
  page: RowPage,
  rowId: string,
  versions: Record<string, number>,
): RowPage {
  return {
    ...page,
    rows: page.rows.map((r) =>
      r.id === rowId ? { ...r, fieldVersions: { ...r.fieldVersions, ...versions } } : r,
    ),
  }
}
