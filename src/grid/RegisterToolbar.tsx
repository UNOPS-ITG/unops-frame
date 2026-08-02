/**
 * The register toolbar: views, import, export.
 *
 * Three governed actions in one strip, and each states something the user would
 * otherwise have to infer:
 *
 * - The view list says which views are *yours*, because a shared view you
 *   cannot edit and one you can look identical until you try.
 * - Import shows what a file would do before it does it. The dry run is the
 *   default path, not a checkbox nobody ticks.
 * - Export says how many rows it did not contain, in the UI as well as in the
 *   file, because the person who clicks it is the person who forwards it.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ApiError,
  exportCsv,
  importCsv,
  listViews,
  type ImportResult,
  type SavedView,
} from '../api/client'

export interface RegisterToolbarProps {
  workspaceId: string
  blueprintId: string
  activeViewId?: string | undefined
  onSelectView: (viewId: string | undefined) => void
  onImported: () => void
}

export function RegisterToolbar({
  workspaceId,
  blueprintId,
  activeViewId,
  onSelectView,
  onImported,
}: RegisterToolbarProps) {
  const [views, setViews] = useState<SavedView[]>([])
  const [importResult, setImportResult] = useState<ImportResult | null>(null)
  const [pendingCsv, setPendingCsv] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
        {views.length > 0 && (
          <label style={{ display: 'flex', gap: '0.375rem', alignItems: 'center' }}>
            <span style={{ font: 'var(--text-body-small)', color: 'var(--color-text-secondary)' }}>
              View
            </span>
            <select
              className="form-select"
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
          </label>
        )}

        <span style={{ marginInlineStart: 'auto', display: 'flex', gap: '0.5rem' }}>
          <input
            ref={fileInput}
            type="file"
            accept=".csv,text/csv"
            style={{ display: 'none' }}
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) void handleFile(file)
              e.target.value = ''
            }}
          />
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={busy}
            onClick={() => fileInput.current?.click()}
          >
            Import CSV
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={busy}
            onClick={() => void handleExport()}
          >
            Export CSV
          </button>
        </span>
      </div>

      {notice !== null && (
        <div role="status" style={{ font: 'var(--text-body-small)', color: 'var(--color-text-secondary)' }}>
          {notice}
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
    </div>
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
    <div
      role="region"
      aria-label="Import preview"
      style={{
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-md)',
        padding: '0.75rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.5rem',
        font: 'var(--text-body-small)',
      }}
    >
      <strong>
        {result.parsedRows.toLocaleString()} rows read · {result.validRows.toLocaleString()} valid
        {blocked && ` · ${result.errors.length.toLocaleString()} problems`}
      </strong>

      {result.unmappedColumns.length > 0 && (
        // Stated, not ignored: a mis-exported file whose columns silently
        // vanish produces rows that look complete and are not.
        <div style={{ color: 'var(--color-warning)' }}>
          These columns matched no field and will be ignored:{' '}
          {result.unmappedColumns.join(', ')}
        </div>
      )}

      {blocked && (
        <>
          <div style={{ color: 'var(--color-danger)' }}>
            Nothing will be written while any row is invalid — a half-applied import cannot be told
            from a finished one.
          </div>
          <ul style={{ margin: 0, paddingInlineStart: '1.25rem', maxHeight: '10rem', overflowY: 'auto' }}>
            {result.errors.slice(0, 50).map((e, i) => (
              <li key={`${e.line}-${e.fieldId ?? ''}-${i}`}>
                Line {e.line}
                {e.fieldId !== null && ` · ${e.fieldId}`}: {e.message}
              </li>
            ))}
          </ul>
          {result.truncatedErrors > 0 && (
            <div>and {result.truncatedErrors.toLocaleString()} more</div>
          )}
        </>
      )}

      <div style={{ display: 'flex', gap: '0.5rem' }}>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          disabled={busy || blocked || result.validRows === 0}
          onClick={onCommit}
        >
          Import {result.validRows.toLocaleString()} rows
        </button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onCancel} disabled={busy}>
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
