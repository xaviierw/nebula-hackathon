import { useState } from 'react'
import { Link } from 'react-router-dom'

import { AcvFileDropzone } from '../../features/acv/components/AcvFileDropzone'
import { AcvIntro } from '../../features/acv/components/AcvIntro'
import { runAcvPrediction } from '../../features/acv/runPrediction'
import { ACV_SUBMISSION_FILENAME, downloadAcvPredictionsCsv } from '../../features/acv/toCsv'
import type { AcvBatchResult, AcvResult } from '../../features/acv/types'

type Status = 'idle' | 'analyzing' | 'done' | 'error'

export function AcvPage() {
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState<Status>('idle')
  const [result, setResult] = useState<AcvBatchResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleFile(selected: File) {
    setFile(selected)
    setStatus('analyzing')
    setResult(null)
    setError(null)

    try {
      setResult(await runAcvPrediction(selected))
      setStatus('done')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Something went wrong.')
      setStatus('error')
    }
  }

  return (
    <div className="space-y-6">
      <Link to="/home" className="text-sm font-medium text-sky-700 hover:text-sky-800">
        &lt;- Back to dashboard
      </Link>

      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">ACV</h1>
        <p className="mt-2 text-sm text-slate-600">
          Rank train cars by how likely their air-conditioning is to be faulty.
        </p>
      </header>

      <AcvIntro />

      <AcvFileDropzone
        onFileSelected={handleFile}
        selectedFile={file}
        disabled={status === 'analyzing'}
      />

      {status === 'analyzing' && <AnalyzingState />}
      {status === 'error' && error !== null && <ErrorState message={error} />}
      {status === 'done' && result !== null && <AcvResults result={result} />}
    </div>
  )
}

function AnalyzingState() {
  return (
    <div role="status" className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-5 py-4">
      <span aria-hidden="true" className="size-4 animate-spin rounded-full border-2 border-slate-300 border-t-sky-600" />
      <p className="text-sm text-slate-600">Ranking ACV faults...</p>
    </div>
  )
}

function AcvResults({ result }: { result: AcvBatchResult }) {
  return (
    <div className="space-y-4">
      <AcvRankingTable result={result} />
      {result.results.map((item, index) => (
        item.ok && item.result !== null ? <AcvResultCard key={`${item.filename}-${index}`} filename={item.filename} result={item.result} /> : (
          <div key={`${item.filename}-${index}`} role="alert" className={item.skipped ? 'rounded-lg border border-amber-200 bg-amber-50 px-5 py-4' : 'rounded-lg border border-red-200 bg-red-50 px-5 py-4'}>
            <p className={item.skipped ? 'text-sm font-semibold text-amber-900' : 'text-sm font-semibold text-red-900'}>{item.skipped ? 'Skipped' : item.filename}</p>
            <p className={item.skipped ? 'mt-1 text-sm text-amber-800' : 'mt-1 text-sm text-red-800'}>{item.skipped ? `${item.filename}: ${item.message}` : (item.message ?? 'This file could not be analysed.')}</p>
          </div>
        )
      ))}
    </div>
  )
}

function AcvRankingTable({ result }: { result: AcvBatchResult }) {
  const rankedFiles = result.results.filter((item) => item.ok && item.result !== null)

  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <div className="flex items-center justify-between gap-4 border-b border-slate-200 px-5 py-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">Final rankings</h2>
          <p className="mt-1 text-sm text-slate-600">Submission-ready ranking for each analysed file.</p>
        </div>
        <button
          type="button"
          disabled={rankedFiles.length === 0}
          onClick={() => downloadAcvPredictionsCsv(result)}
          className="shrink-0 rounded-md bg-sky-700 px-3 py-2 text-sm font-semibold text-white hover:bg-sky-800 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2"
        >
          Download {ACV_SUBMISSION_FILENAME}
        </button>
      </div>
      {rankedFiles.length === 0 ? (
        <p className="px-5 py-5 text-sm text-slate-500">No files were successfully analysed.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[32rem] text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th scope="col" className="px-5 py-3 font-medium">File</th>
                <th scope="col" className="px-5 py-3 font-medium">Ranked cars</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rankedFiles.map((item) => (
                <tr key={item.filename}>
                  <td className="whitespace-nowrap px-5 py-3 font-medium text-slate-900">{item.filename}</td>
                  <td className="px-5 py-3 font-mono text-xs text-slate-700">{item.result!.ranked_cars.join('|')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function AcvResultCard({ filename, result }: { filename: string; result: AcvResult }) {
  const priorityCar = result.ranked_cars[0]
  const priorityScore = result.scores[priorityCar]
  const nextScore = result.ranked_cars.length > 1 ? result.scores[result.ranked_cars[1]] : undefined
  const lead = priorityScore !== undefined && nextScore !== undefined ? priorityScore - nextScore : undefined
  const hasSignalWarning = result.warnings.some((warning) => warning.code === 'DISAGREEING_FEATURES')

  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-5 py-4">
        <h2 className="text-sm font-semibold text-slate-900">{filename}</h2>
        <p className="mt-1 text-sm text-slate-600">Cars are ordered from highest to lowest inspection priority.</p>
      </div>
      <div className="grid gap-3 border-b border-slate-200 bg-slate-50 px-5 py-4 sm:grid-cols-3">
        <Insight label="Priority inspection" value={priorityCar ?? 'None'} detail="Highest relative fault score" />
        <Insight label="Cars compared" value={String(result.ranked_cars.length)} detail="Every car in this file" />
        <Insight
          label="Rank separation"
          value={lead !== undefined ? `${(lead * 100).toFixed(1)} pts` : 'N/A'}
          detail={lead !== undefined && lead >= 0.1 ? 'Top score minus #2' : 'Close ranking; inspect together'}
        />
      </div>
      <div className={`border-b px-5 py-3 text-xs leading-relaxed ${hasSignalWarning ? 'border-amber-200 bg-amber-50 text-amber-900' : 'border-slate-100 bg-white text-slate-600'}`}>
        {hasSignalWarning
          ? 'The shortfall and delivered-cooling signals disagree on the top car. Review this ranking alongside maintenance records.'
          : 'The primary ranking signals agree on the top car. Use the order to prioritise inspection, not as a confirmed diagnosis.'}
      </div>
      <ol className="divide-y divide-slate-100">
        {result.ranked_cars.map((car, index) => (
          <li key={car} className="flex items-center justify-between px-5 py-3">
            <span className="flex items-center gap-3 text-sm text-slate-900"><span className="w-6 text-right font-mono text-xs text-slate-400">{index + 1}</span><span className="font-medium">{car}</span></span>
            {result.scores[car] !== undefined && <span className="text-sm tabular-nums text-slate-600">{(result.scores[car] * 100).toFixed(1)} pts</span>}
          </li>
        ))}
      </ol>
      {result.warnings.length > 0 && <div className="border-t border-amber-200 bg-amber-50 px-5 py-4">{result.warnings.map((warning) => <p key={`${warning.code}-${warning.message}`} className="text-sm text-amber-900">{warning.message}</p>)}</div>}
    </section>
  )
}

function Insight({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 truncate text-lg font-semibold tabular-nums text-slate-900" title={value}>{value}</p>
      <p className="mt-0.5 text-xs text-slate-500">{detail}</p>
    </div>
  )
}

function ErrorState({ message }: { message: string }) {
  return (
    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-5 py-4">
      <p className="text-sm font-semibold text-red-900">That file could not be analysed</p>
      <p className="mt-1 whitespace-pre-line text-sm leading-relaxed text-red-800">{message}</p>
    </div>
  )
}
