import { useState } from 'react'

import { downloadRailPredictions } from '../toCsv'
import type { RailBatch, RailQueueEntry } from '../types'
import { exportState } from '../workspace'

export function RailResultsQueue({ batch, selectedId, processing, onSelect, onRetry, onExclude }: {
  batch: RailBatch
  selectedId: string | null
  processing: boolean
  onSelect: (id: string) => void
  onRetry: (entry: RailQueueEntry, replacement?: File) => void
  onExclude: (entry: RailQueueEntry) => void
}) {
  const [filter, setFilter] = useState('all')
  const { completed, unresolved, excluded, canExport } = exportState(batch)
  const failed = batch.entries.filter((entry) => entry.status === 'error').length
  const done = batch.entries.filter((entry) => entry.status === 'done').length
  const flagged = batch.entries.filter((entry) => entry.analysis && entry.analysis.prediction !== 'Normal').length
  const visible = batch.entries.filter((entry) => {
    if (filter === 'flagged') return entry.analysis && entry.analysis.prediction !== 'Normal'
    if (filter === 'awaiting') return entry.status === 'done' && entry.review.status === 'awaiting_review'
    if (filter === 'errors') return entry.status === 'error'
    return true
  })

  return (
    <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-4 sm:p-5" aria-label="Results queue">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Results queue</h2>
          <p role="status" className="mt-1 text-sm text-slate-600">{done} completed · {flagged} flagged · {failed} failed · {batch.entries.length} total</p>
        </div>
        <label className="text-xs font-medium text-slate-600">Show
          <select aria-label="Filter recordings" className="ml-2 rounded-md border border-slate-300 bg-white px-2 py-2 text-sm" value={filter} onChange={(event) => setFilter(event.target.value)}>
            <option value="all">All recordings</option><option value="flagged">Flagged</option><option value="awaiting">Awaiting review</option><option value="errors">Failed</option>
          </select>
        </label>
      </div>
      {processing && <p className="text-xs text-sky-800">Processing one file at a time. Keep this page open; completed results are saved as they arrive.</p>}
      <ul className="max-h-96 space-y-2 overflow-y-auto" aria-label="Recording results">
        {visible.map((entry) => (
          <li key={entry.id} data-entry-id={entry.id} className={`rounded-md border p-3 ${entry.id === selectedId ? 'border-sky-500 bg-sky-50' : 'border-slate-200'}`}>
            <button type="button" onClick={() => onSelect(entry.id)} aria-pressed={entry.id === selectedId} aria-label={`View ${entry.fileName}`}
              className="flex w-full flex-col gap-2 text-left focus-visible:outline-2 focus-visible:outline-sky-600 sm:flex-row sm:items-center sm:justify-between">
              <span className="min-w-0 break-all text-sm font-semibold text-slate-900">{entry.fileName}</span>
              <span className="flex shrink-0 flex-wrap gap-2 text-xs">
                <span className={entry.status === 'error' ? 'font-semibold text-red-800' : entry.analysis?.prediction === 'Normal' ? 'font-semibold text-emerald-800' : 'font-semibold text-slate-700'}>
                  {entry.status === 'done' ? entry.analysis?.prediction : entry.status === 'error' ? 'Failed' : entry.status === 'analysing' ? 'Analysing…' : 'Queued'}
                </span>
                {entry.status === 'done' && <span className="text-slate-500">{entry.review.status === 'reviewed' ? 'Reviewed' : 'Awaiting review'}</span>}
                {entry.excluded && <span className="font-semibold text-amber-800">Excluded from export</span>}
              </span>
            </button>
            {entry.status === 'error' && (
              <div className="mt-2 space-y-2">
                <p className="break-words text-xs text-red-700">{entry.error}</p>
                <div className="flex flex-wrap gap-3 text-xs font-semibold text-sky-800">
                  <button type="button" disabled={processing} onClick={() => onRetry(entry)} className="underline disabled:opacity-40">Retry</button>
                  <label className="cursor-pointer underline">Reselect file
                    <input type="file" accept=".csv,text/csv" disabled={processing} className="mt-1 block w-full max-w-56 text-xs font-normal"
                      aria-label={`Reselect ${entry.fileName}`} onChange={(event) => {
                        const file = event.target.files?.[0]
                        if (file) onRetry(entry, file)
                        event.target.value = ''
                      }} />
                  </label>
                  <button type="button" disabled={processing} onClick={() => onExclude(entry)} className="underline disabled:opacity-40">{entry.excluded ? 'Include in batch export' : 'Exclude from batch export'}</button>
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
      {visible.length === 0 && <p className="text-sm text-slate-500">No recordings match this filter.</p>}
      <div className="space-y-2 border-t border-slate-200 pt-4">
        <button type="button" disabled={!canExport || processing} onClick={() => downloadRailPredictions(completed.map((entry) => entry.analysis!))}
          className="w-full rounded-md bg-sky-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-sky-800 disabled:cursor-not-allowed disabled:opacity-40 sm:w-auto">
          Download rail_predictions.csv ({completed.length} rows)
        </button>
        <p className="text-xs leading-relaxed text-slate-500">{unresolved.length > 0
          ? `${unresolved.length} unresolved file(s). Wait for analysis, retry failed files, or explicitly exclude them before exporting.`
          : `Exports all ${completed.length} successful predictions in this batch in upload order, regardless of the current filter.`}</p>
        {excluded.length > 0 && <p className="text-xs font-semibold text-amber-800">Partial batch: {excluded.length} excluded file(s) will not appear in the CSV.</p>}
      </div>
    </section>
  )
}
