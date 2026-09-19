import { useState } from 'react'
import { Link } from 'react-router-dom'

import { DoorIntro } from '../../features/door/components/DoorIntro'
import { DoorResultsTable } from '../../features/door/components/DoorResultsTable'
import { DoorSummary } from '../../features/door/components/DoorSummary'
import { DoorWarnings } from '../../features/door/components/DoorWarnings'
import { FileDropzone } from '../../features/door/components/FileDropzone'
import { runDoorPrediction } from '../../features/door/runPrediction'
import { SUBMISSION_FILENAME, downloadPredictionsCsv } from '../../features/door/toCsv'
import type { DoorResult } from '../../features/door/types'

/**
 * The Door subsystem page.
 *
 * runDoorPrediction() sends the selected recording to the shared authenticated
 * API. The page keeps loading, empty and readable backend-error states separate.
 */

type Status = 'idle' | 'analyzing' | 'done' | 'error'

export function DoorPage() {
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState<Status>('idle')
  const [result, setResult] = useState<DoorResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleFile(selected: File) {
    setFile(selected)
    setStatus('analyzing')
    setResult(null)
    setError(null)

    try {
      setResult(await runDoorPrediction(selected))
      setStatus('done')
    } catch (caught) {
      // The Python messages are written for end users, so show them verbatim.
      setError(caught instanceof Error ? caught.message : 'Something went wrong.')
      setStatus('error')
    }
  }

  return (
    <div className="space-y-6">
      <Link to="/home" className="text-sm font-medium text-sky-700 hover:text-sky-800">
        ← Back to dashboard
      </Link>

      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Door</h1>
        <p className="mt-2 text-sm text-slate-600">
          Find every door cycle in a recording and flag the ones where the motor strained.
        </p>
      </header>

      <DoorIntro />

      <FileDropzone
        onFileSelected={handleFile}
        selectedFile={file}
        disabled={status === 'analyzing'}
      />

      {status === 'analyzing' && <AnalyzingState />}

      {status === 'error' && error !== null && <ErrorState message={error} />}

      {status === 'done' && result !== null && (
        <>
          {result.detail.length === 0 ? (
            <EmptyState />
          ) : (
            <>
              <DoorSummary detail={result.detail} />

              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={() => downloadPredictionsCsv(result.detail)}
                  className="rounded-md bg-sky-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-sky-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2"
                >
                  ⭳ Download {SUBMISSION_FILENAME}
                </button>
              </div>

              <DoorWarnings warnings={result.warnings} />
              <DoorResultsTable detail={result.detail} />

              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={() => downloadPredictionsCsv(result.detail)}
                  className="rounded-md bg-sky-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-sky-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2"
                >
                  ⭳ Download {SUBMISSION_FILENAME}
                </button>
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}

function AnalyzingState() {
  return (
    <div
      role="status"
      className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-5 py-4"
    >
      <span
        aria-hidden="true"
        className="size-4 animate-spin rounded-full border-2 border-slate-300 border-t-sky-600"
      />
      <p className="text-sm text-slate-600">Looking for door cycles…</p>
    </div>
  )
}

/**
 * predict_stream returns completely empty frames when it finds no cycles, so
 * the live API may well send `detail: []`. Saying so beats an empty table.
 */
function EmptyState() {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-5 py-10 text-center">
      <p className="text-sm font-medium text-slate-900">No door cycles found in this file.</p>
      <p className="mt-1 text-sm text-slate-500">
        Door recordings contain the motor current sampled every 20 ms across many open and close
        cycles. This file does not appear to have any.
      </p>
    </div>
  )
}

function ErrorState({ message }: { message: string }) {
  return (
    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-5 py-4">
      <p className="text-sm font-semibold text-red-900">That file could not be analysed</p>
      {/* whitespace-pre-line: the backend messages are deliberately multi-line. */}
      <p className="mt-1 whitespace-pre-line text-sm leading-relaxed text-red-800">{message}</p>
    </div>
  )
}
