/**
 * The register toolbar: views, filter, import, export.
 *
 * Four governed actions in one strip, and each states something the user would
 * otherwise have to infer:
 *
 * - The view list says which views are *yours*, because a shared view you
 *   cannot edit and one you can look identical until you try.
 * - The filter panel stays mounted while a filter is applying. It used to
 *   unmount on every refetch, which threw away a half-typed view name.
 * - Import shows what a file would do before it does it. The dry run is the
 *   default path, not a checkbox nobody ticks.
 * - Export says how many rows it did not contain, in the UI as well as in the
 *   file, because the person who clicks it is the person who forwards it.
 */

import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import {
  ApiError,
  createView,
  exportCsv,
  importCsv,
  listViews,
  type ImportResult,
  type SavedView,
} from '../api/client'
import { Icon } from '../app/icons'
import { FilterBuilder } from './FilterBuilder'
import type { Blueprint } from './contract'

export interface RegisterToolbarProps {
  workspaceId: string
  blueprintId: string
  blueprint: Blueprint
  activeViewId?: string | undefined
  onSelectView: (viewId: string | undefined) => void
  onImported: () => void
  onFilter: (filter: Record<string, unknown> | null) => void
  onAddRow?: () => void
  /** The register's named intake form (FM-1), when one exists. Rendered
   * beside "New row" under the form's own name — "Report a risk" is an act
   * someone recognises as theirs; "Open form" is furniture. */
  formName?: string
  onOpenForm?: () => void
  /** Rendered at the end of the strip. The toolbar does not compute it: the
   * withheld count belongs to the page that fetched it, and a toolbar deriving
   * its own would be a second number that then has to agree with the first. */
  annotation?: ReactNode
}

export function RegisterToolbar({
  workspaceId,
  blueprintId,
  blueprint,
  activeViewId,
  onSelectView,
  onImported,
  onFilter,
  onAddRow,
  formName,
  onOpenForm,
  annotation,
}: RegisterToolbarProps) {
  const [views, setViews] = useState<SavedView[]>([])
  const [importResult, setImportResult] = useState<ImportResult | null>(null)
  const [pendingCsv, setPendingCsv] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [filtering, setFiltering] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  const saveView = useCallback(
    async (name: string, filter: Record<string, unknown> | null) => {
      setBusy(true)
      try {
        const saved = await createView(workspaceId, blueprintId, { name, filter })
        setViews((prev) => [...prev, saved])
        // Its warnings, if any, are carried on the view rather than swallowed:
        // a sort with no slot saves fine and behaves differently, and the person
        // who later opens it is rarely the person who saved it.
        setNotice(
          saved.warnings.length > 0
            ? `Saved "${saved.name}" — ${saved.warnings[0]?.message ?? ''}`
            : `Saved "${saved.name}"`,
        )
      } catch (e) {
        setNotice(e instanceof ApiError ? e.message : 'The view could not be saved')
      } finally {
        setBusy(false)
      }
    },
    [workspaceId, blueprintId],
  )

  useEffect(() => {
    let cancelled = false
    listViews(workspaceId, blueprintId)
      .then((v) => {
        if (!cancelled) setViews(v)
      })
      .catch(() => {
        // A register whose view list will not load is still a usable register.
        if (!cancelled) setViews([])
      })
    return () => {
      cancelled = true
    }
  }, [workspaceId, blueprintId])

  const handleFile = useCallback(
    async (file: File) => {
      setBusy(true)
      setNotice(null)
      try {
        const text = await file.text()
        // Dry run first, always. The user sees exactly what will happen and
        // what will not before anything is written.
        const result = await importCsv(workspaceId, blueprintId, text, true)
        setPendingCsv(text)
        setImportResult(result)
      } catch (e) {
        setNotice(e instanceof ApiError ? e.message : 'The file could not be read')
      } finally {
        setBusy(false)
      }
    },
    [workspaceId, blueprintId],
  )

  const commitImport = useCallback(async () => {
    if (pendingCsv === null) return
    setBusy(true)
    try {
      const result = await importCsv(workspaceId, blueprintId, pendingCsv, false)
      setImportResult(null)
      setPendingCsv(null)
      setNotice(`${result.writtenRows.toLocaleString()} rows imported`)
      onImported()
    } catch (e) {
      setNotice(e instanceof ApiError ? e.message : 'The import could not be completed')
    } finally {
      setBusy(false)
    }
  }, [pendingCsv, workspaceId, blueprintId, onImported])

  const handleExport = useCallback(async () => {
    setBusy(true)
    setNotice(null)
    try {
      const result = await exportCsv(workspaceId, blueprintId)
      download(`${blueprintId}.csv`, result.csv)
      setNotice(
        result.withheld > 0
          ? `Exported ${result.visible.toLocaleString()} rows. ${result.withheld.toLocaleString()} you cannot see were not included.`
          : `Exported ${result.visible.toLocaleString()} rows.`,
      )
    } catch (e) {
      setNotice(e instanceof ApiError ? e.message : 'The export could not be produced')
    } finally {
      setBusy(false)
    }
  }, [workspaceId, blueprintId])

  return (
    <>
      <div className="register__toolbar">
        {views.length > 0 && (
          <div className="register__toolbar-group">
            <label className="register__control-label" htmlFor="register-view">
              View
            </label>
            <select
              id="register-view"
              className="ops-select"
              value={activeViewId ?? ''}
              onChange={(e) => onSelectView(e.target.value === '' ? undefined : e.target.value)}
            >
              <option value="">All rows</option>
              {views.map((v) => (
                <option key={v.id} value={v.id}>
                  {/* Marked, because a shared view you can edit and one you
                      cannot look identical until you try. */}
                  {v.name}
                  {v.isMine ? '' : ` (${v.author.replace(/^dev-bypass:/, '')})`}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="register__toolbar-group">
          {onAddRow && (
            <>
              <button type="button" className="btn btn--primary btn--sm" onClick={onAddRow}>
                <Icon.Plus />
                New row
              </button>
              {onOpenForm !== undefined && formName !== undefined && (
                <button type="button" className="btn btn--secondary btn--sm" onClick={onOpenForm}>
                  <Icon.Fields />
                  {formName}
                </button>
              )}
              <span className="register__divider" aria-hidden="true" />
            </>
          )}

          <button
            type="button"
            className="btn btn--ghost btn--sm"
            aria-expanded={filtering}
            onClick={() => setFiltering((f) => !f)}
          >
            <Icon.Filter />
            {filtering ? 'Hide filter' : 'Filter'}
          </button>

          <span className="register__divider" aria-hidden="true" />

          <input
            ref={fileInput}
            type="file"
            accept=".csv,text/csv"
            className="visually-hidden"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) void handleFile(file)
              e.target.value = ''
            }}
          />
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            disabled={busy}
            onClick={() => fileInput.current?.click()}
          >
            <Icon.Upload />
            Import CSV
          </button>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            disabled={busy}
            onClick={() => void handleExport()}
          >
            <Icon.Download />
            Export CSV
          </button>
        </div>

        {annotation !== undefined && (
          <div className="register__toolbar-group register__toolbar-group--end">{annotation}</div>
        )}
      </div>

      {filtering && (
        <div className="register__filter">
          <FilterBuilder
            blueprint={blueprint}
            busy={busy}
            onApply={onFilter}
            onSaveView={(name, filter) => void saveView(name, filter)}
          />
        </div>
      )}

      {notice !== null && (
        <div className="notice notice--info" role="status">
          <div className="notice__body">{notice}</div>
          <button type="button" className="btn btn--ghost btn--sm" onClick={() => setNotice(null)}>
            Dismiss
          </button>
        </div>
      )}

      {importResult !== null && (
        <ImportPreview
          result={importResult}
          busy={busy}
          onCommit={() => void commitImport()}
          onCancel={() => {
            setImportResult(null)
            setPendingCsv(null)
          }}
        />
      )}
    </>
  )
}

function ImportPreview({
  result,
  busy,
  onCommit,
  onCancel,
}: {
  result: ImportResult
  busy: boolean
  onCommit: () => void
  onCancel: () => void
}) {
  const blocked = result.errors.length > 0

  return (
    <div className="import" role="region" aria-label="Import preview">
      <strong className="import__summary">
        {result.parsedRows.toLocaleString()} rows read · {result.validRows.toLocaleString()} valid
        {blocked && ` · ${result.errors.length.toLocaleString()} problems`}
      </strong>

      {result.unmappedColumns.length > 0 && (
        // Stated, not ignored: a mis-exported file whose columns silently
        // vanish produces rows that look complete and are not.
        <div className="import__warning">
          These columns matched no field and will be ignored: {result.unmappedColumns.join(', ')}
        </div>
      )}

      {blocked && (
        <>
          <div className="import__error">
            Nothing will be written while any row is invalid — a half-applied import cannot be told
            from a finished one.
          </div>
          <ul className="import__errors scrollable">
            {result.errors.slice(0, 50).map((e, i) => (
              <li key={`${e.line}-${e.fieldId ?? ''}-${i}`}>
                Line {e.line}
                {e.fieldId !== null && ` · ${e.fieldId}`}: {e.message}
              </li>
            ))}
          </ul>
          {result.truncatedErrors > 0 && (
            <div className="import__error">and {result.truncatedErrors.toLocaleString()} more</div>
          )}
        </>
      )}

      <div className="import__actions">
        <button
          type="button"
          className="btn btn--primary btn--sm"
          disabled={busy || blocked || result.validRows === 0}
          onClick={onCommit}
        >
          Import {result.validRows.toLocaleString()} {result.validRows === 1 ? 'row' : 'rows'}
        </button>
        <button type="button" className="btn btn--ghost btn--sm" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
      </div>
    </div>
  )
}

function download(filename: string, text: string): void {
  // A BOM, so Excel opens UTF-8 correctly on Windows. Without it, every
  // non-ASCII name in the file — which at UNOPS is most of them — renders as
  // mojibake, and the user concludes the export is broken.
  const blob = new Blob(['﻿', text], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename

  // Attached before clicking and revoked on a later task, not immediately.
  // `click()` only *schedules* the download; revoking in the same tick pulls
  // the blob out from under it and the browser cancels — silently, and more
  // often on a large file, which is the one the user most wanted.
  anchor.style.display = 'none'
  document.body.appendChild(anchor)
  anchor.click()
  setTimeout(() => {
    anchor.remove()
    URL.revokeObjectURL(url)
  }, 30_000)
}
