import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { RailFileDropzone } from '../../features/rail/components/RailFileDropzone'
import { RailResultCard } from '../../features/rail/components/RailResultCard'
import { RailResultsQueue } from '../../features/rail/components/RailResultsQueue'
import { runRailPredictionBatch } from '../../features/rail/runPrediction'
import type { RailBatch, RailQueueEntry, RailReview } from '../../features/rail/types'
import { useRailWorkspace } from '../../features/rail/useRailWorkspace'
import { createEntries, MAX_RAIL_FILE_BYTES } from '../../features/rail/workspace'

export function RailCorrugationPage() {
  const { workspace, setWorkspace, storageError } = useRailWorkspace()
  const [batchId, setBatchId] = useState<string | null>(workspace.batches[0]?.id ?? null)
  const [selectedId, setSelectedId] = useState<string | null>(workspace.batches[0]?.entries[0]?.id ?? null)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const files = useRef(new Map<string, File>())
  const controller = useRef<AbortController | null>(null)
  const batch = workspace.batches.find((candidate) => candidate.id === batchId)
  const selected = batch?.entries.find((entry) => entry.id === selectedId)

  useEffect(() => () => { controller.current?.abort() }, [])

  function updateEntry(targetBatch: string, id: string, patch: Partial<RailQueueEntry>) {
    setWorkspace((current) => ({ ...current, batches: current.batches.map((candidate) => candidate.id !== targetBatch
      ? candidate : { ...candidate, entries: candidate.entries.map((entry) => entry.id === id ? { ...entry, ...patch } : entry) }) }))
  }

  function newBatch(): RailBatch {
    const created: RailBatch = { id: crypto.randomUUID(), createdAt: new Date().toISOString(), entries: [] }
    setWorkspace((current) => ({ ...current, batches: [created, ...current.batches] }))
    setBatchId(created.id)
    setSelectedId(null)
    setError(null)
    return created
  }

  async function processEntries(targetBatch: string, entries: RailQueueEntry[]) {
    const request = new AbortController()
    controller.current = request
    setProcessing(true)
    try {
      const pending = entries.flatMap((entry) => {
        const file = files.current.get(entry.id)
        return entry.status === 'queued' && file ? [{ entry, file }] : []
      })
      if (pending.length === 0) return
      pending.forEach(({ entry }) => {
        updateEntry(targetBatch, entry.id, { status: 'analysing', error: null, excluded: false })
      })

      const outcomes = await runRailPredictionBatch(pending.map(({ file }) => file), request.signal)
      if (!request.signal.aborted) outcomes.forEach((outcome, index) => {
        const entry = pending[index].entry
        if (outcome.ok) {
          const analysis = outcome.analysis
          updateEntry(targetBatch, entry.id, { status: 'done', analysis, analysedAt: new Date().toISOString() })
          files.current.delete(entry.id)
        } else {
          updateEntry(targetBatch, entry.id, { status: 'error', error: outcome.message })
        }
      })
    } catch (caught) {
      if (!request.signal.aborted) {
        const message = caught instanceof Error ? caught.message : 'Analysis failed. Please retry.'
        entries.filter((entry) => entry.status === 'queued').forEach((entry) => {
          updateEntry(targetBatch, entry.id, { status: 'error', error: message })
        })
      }
    } finally {
      if (!request.signal.aborted) { controller.current = null; setProcessing(false) }
    }
  }

  function handleFiles(selectedFiles: File[]) {
    if (!selectedFiles.length || controller.current) return
    setError(null)
    try {
      const entries = createEntries(selectedFiles, batch?.entries)
      const target = batch ?? newBatch()
      entries.forEach((entry, index) => files.current.set(entry.id, selectedFiles[index]))
      setWorkspace((current) => ({ ...current, batches: current.batches.map((candidate) => candidate.id === target.id
        ? { ...candidate, entries: [...candidate.entries, ...entries] } : candidate) }))
      setSelectedId(entries[0].id)
      void processEntries(target.id, entries)
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Could not add those files.') }
  }

  function retry(entry: RailQueueEntry, replacement?: File) {
    if (!batch || controller.current) return
    const file = replacement ?? files.current.get(entry.id)
    if (!file) { setError(`Reselect ${entry.fileName} in the queue to retry. Raw recordings are not saved in this browser.`); return }
    if (file.name !== entry.fileName) { setError(`Please select a file named ${entry.fileName}, or add this recording to a new batch.`); return }
    if (!file.name.toLowerCase().endsWith('.csv') || file.size > MAX_RAIL_FILE_BYTES) { setError('Select a CSV of 25 MiB or less.'); return }
    setError(null)
    files.current.set(entry.id, file)
    const queued: RailQueueEntry = { ...entry, status: 'queued', size: file.size, error: null, excluded: false }
    updateEntry(batch.id, entry.id, queued)
    void processEntries(batch.id, [queued])
  }

  function updateReview(patch: Partial<RailReview>) {
    if (!batch || !selected) return
    updateEntry(batch.id, selected.id, { review: { ...selected.review, ...patch, updatedAt: new Date().toISOString() } })
  }

  return (
    <div className="space-y-6">
      <Link to="/home" className="text-sm font-medium text-sky-700 hover:text-sky-800">← Back to dashboard</Link>
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Rail Corrugation</h1>
        <p className="mt-2 text-sm text-slate-600">Analyse recordings, review the evidence and export predictions for your batch.</p>
      </header>
      <div className="rounded-lg border border-sky-200 bg-sky-50 px-5 py-4">
        <p className="text-sm font-semibold text-sky-950">Expected recordings</p>
        <p className="mt-1 text-sm leading-relaxed text-sky-900">Each CSV must contain 10,000 measurements across the 129 columns defined in the Rail Corrugation dataset.</p>
      </div>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <label className="min-w-0 flex-1 text-sm font-medium text-slate-700">Saved batches
          <select aria-label="Saved batches" disabled={processing || workspace.batches.length === 0} value={batchId ?? ''}
            className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 text-sm disabled:opacity-60"
            onChange={(event) => { setBatchId(event.target.value); setSelectedId(workspace.batches.find((item) => item.id === event.target.value)?.entries[0]?.id ?? null); setError(null) }}>
            {workspace.batches.length === 0 && <option value="">Upload recordings to begin</option>}
            {workspace.batches.map((item) => <option key={item.id} value={item.id}>{new Date(item.createdAt).toLocaleString()} · {item.entries.length} recording(s) · {item.id.slice(0, 6)}</option>)}
          </select>
        </label>
        <button type="button" disabled={processing} onClick={() => newBatch()} className="rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40">New batch</button>
      </div>
      <p className="text-xs text-slate-500">Results and review records stay in this browser on this device. Raw CSVs are not retained. Download reports to share or back up your reviews.</p>
      {storageError && <p role="alert" className="rounded-md border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">{storageError}</p>}
      <RailFileDropzone onFilesSelected={handleFiles} disabled={processing} />
      {error && <p role="alert" className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-900">{error}</p>}
      {batch && batch.entries.length > 0 && <RailResultsQueue key={batch.id} batch={batch} selectedId={selectedId} processing={processing}
        onSelect={setSelectedId} onRetry={retry} onExclude={(entry) => updateEntry(batch.id, entry.id, { excluded: !entry.excluded })} />}
      {selected?.status === 'done' && <RailResultCard key={selected.id} entry={selected} onReviewChange={updateReview} />}
      {selected && selected.status !== 'done' && <div role={selected.status === 'error' ? 'alert' : 'status'} className="rounded-lg border border-slate-200 bg-white p-5 text-sm text-slate-700">
        <p className="break-all font-semibold">{selected.fileName}</p>
        <p className="mt-1">{selected.status === 'error' ? selected.error : selected.status === 'analysing' ? 'Extracting vibration features and classifying…' : 'Waiting in the analysis queue.'}</p>
      </div>}
    </div>
  )
}
