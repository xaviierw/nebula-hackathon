import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { downloadShmCsv, MAX_FILE_BYTES, MAX_FILES, predictShm } from '../../features/shm/prediction'
import type { ShmPrediction } from '../../features/shm/prediction'

type Row = { file: File; status: 'ready' | 'running' | 'done' | 'error'; result?: ShmPrediction; error?: string }
const button = 'rounded-md bg-sky-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-sky-800 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600'

export function ShmPage() {
  const [rows, setRows] = useState<Row[]>([])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const busy = useRef(false)
  const input = useRef<HTMLInputElement>(null)
  const completed = rows.filter(row => row.status === 'done').length
  const processed = rows.filter(row => row.status === 'done' || row.status === 'error').length
  const allDone = rows.length > 0 && completed === rows.length && !running

  function selectFiles(files: File[]) {
    if (busy.current) return
    // Replacing a selection always invalidates old predictions/downloads.
    setRows([])
    setError('')
    if (!files.length) return
    if (files.length > MAX_FILES) {
      setError(`Choose up to ${MAX_FILES} recordings at a time.`)
      return
    }
    if (new Set(files.map(file => file.name)).size !== files.length) {
      setError('Two files have the same filename. Select recordings with unique filenames.')
      return
    }
    const invalid = files.find(file => !file.name.toLowerCase().endsWith('.csv') || file.size === 0 || file.size > MAX_FILE_BYTES)
    if (invalid) {
      setError(`${invalid.name}: choose a nonempty CSV no larger than 16 MiB.`)
      return
    }
    setRows(files.map(file => ({ file, status: 'ready' })))
  }

  async function analyse() {
    if (busy.current || !rows.length) return
    busy.current = true
    setRunning(true)
    setError('')
    const batch: Row[] = rows.map(row => ({ file: row.file, status: 'ready' }))
    setRows([...batch])
    let modelId: string | undefined
    // One upload at a time bounds memory and gives useful per-recording progress.
    try {
      for (let i = 0; i < batch.length; i++) {
        batch[i] = { ...batch[i], status: 'running' }
        setRows([...batch])
        try {
          const result = await predictShm(batch[i].file)
          if (modelId !== undefined && result.model_id !== modelId) {
            throw new Error('The model changed during this batch. Run the batch again before downloading.')
          }
          modelId = result.model_id
          batch[i] = { ...batch[i], result, status: 'done' }
        } catch (caught) {
          batch[i] = { ...batch[i], status: 'error', error: caught instanceof Error ? caught.message : 'Prediction failed.' }
        }
        setRows([...batch])
      }
    } finally {
      busy.current = false
      setRunning(false)
    }
  }

  return (
    <div className="space-y-6">
      <Link to="/home" className="text-sm font-medium text-sky-700 hover:text-sky-800">← Back to dashboard</Link>
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Structural health monitoring</h1>
        <p className="mt-2 text-sm text-slate-600">Estimate cumulative fatigue damage from a complete stress recording.</p>
      </header>

      <section className="rounded-lg border border-slate-200 bg-white p-5 text-sm text-slate-600">
        <h2 className="font-semibold text-slate-900">One recording, one damage estimate</h2>
        <p className="mt-2">Upload the supplied SHM CSV files with 581,120 stress observations in one column and no header. Keep the original stress values and filenames.</p>
        <p className="mt-2">The model counts stress cycles and combines their contributions to estimate fatigue damage accumulated during each recording. This value is not a failure probability or remaining-life estimate.</p>
      </section>

      <section
        className={`rounded-lg border-2 border-dashed p-8 text-center ${dragging ? 'border-sky-500 bg-sky-50' : 'border-slate-300 bg-white'}`}
        aria-label="Upload stress recordings"
        onDragOver={event => { event.preventDefault(); if (!running) setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={event => { event.preventDefault(); setDragging(false); selectFiles(Array.from(event.dataTransfer.files)) }}
      >
        <p className="font-medium text-slate-900">Drop stress CSV files here</p>
        <p className="mt-1 text-sm text-slate-500">Choose multiple files, including all 16 test recordings. Up to 32 files, 16 MiB each.</p>
        <input ref={input} type="file" multiple accept=".csv" className="sr-only" aria-label="Choose stress CSV files" disabled={running}
          onChange={event => { selectFiles(Array.from(event.target.files ?? [])); event.target.value = '' }} />
        <button type="button" className={`${button} mt-4`} disabled={running} onClick={() => input.current?.click()}>Choose CSV files</button>
      </section>

      {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
      {rows.length > 0 && <>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p role="status" aria-live="polite" className="text-sm text-slate-600">
            {running ? `Processing recordings: ${processed} of ${rows.length} finished…` : `${rows.length} recording${rows.length === 1 ? '' : 's'} selected · ${completed} predictions ready`}
          </p>
          <button type="button" className={button} disabled={running} onClick={analyse}>{running ? 'Analysing…' : processed > 0 ? 'Run again' : 'Estimate fatigue damage'}</button>
        </div>
        {running && <progress className="h-2 w-full accent-sky-700" value={processed} max={rows.length} aria-label="Recording progress" />}
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Estimated cumulative fatigue damage per recording</caption>
            <thead className="bg-slate-50 text-slate-600"><tr><th scope="col" className="p-4">Recording</th><th scope="col" className="p-4">Status</th><th scope="col" className="p-4 text-right">Estimated damage</th></tr></thead>
            <tbody>{rows.map(row => <tr key={row.file.name} className="border-t border-slate-100 align-top">
              <th scope="row" className="break-all p-4 font-medium text-slate-900">{row.file.name}</th>
              <td className="max-w-sm p-4 text-slate-600">{row.status === 'error' ? <span role="alert" className="text-red-700">{row.error}</span> : ({ ready: 'Ready', running: 'Counting stress cycles…', done: 'Complete' }[row.status])}</td>
              <td className="p-4 text-right font-mono tabular-nums text-slate-900">{row.result ? row.result.prediction.toPrecision(7) : '—'}</td>
            </tr>)}</tbody>
          </table>
        </div>
        {!running && rows.some(row => row.status === 'error') && <p className="text-sm text-red-700">Correct the failed recordings and select the batch again. Download becomes available when every selected recording has a prediction.</p>}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-slate-500">The CSV includes original filenames and full-precision predictions.</p>
          <button type="button" className={button} disabled={!allDone} onClick={() => {
            try { downloadShmCsv(rows.map(row => row.result!)) }
            catch (caught) { setError(caught instanceof Error ? caught.message : 'Download failed.') }
          }}>Download shm_predictions.csv</button>
        </div>
      </>}
    </div>
  )
}
