import { useId } from 'react'

import { downloadRailPrediction } from '../toCsv'
import { downloadReviewReport } from '../report'
import { finding, nextStep } from '../review'
import type { RailQueueEntry, RailReview } from '../types'
import { RailEvidencePanel } from './RailEvidencePanel'
import { RailReviewChecklist } from './RailReviewChecklist'
import { RailReviewRecord } from './RailReviewRecord'
import { RailTrackDiagram } from './RailTrackDiagram'

export function RailResultCard({ entry, onReviewChange }: {
  entry: RailQueueEntry
  onReviewChange: (patch: Partial<RailReview>) => void
}) {
  const headingId = useId()
  const result = entry.analysis
  if (!result) return null
  const isNormal = result.prediction === 'Normal'

  return (
    <section aria-labelledby={headingId} className="space-y-5 rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
      <div>
        <p className="break-all text-xs font-semibold uppercase tracking-wide text-slate-500">
          Finding for {result.file_id}
        </p>
        <div role="status">
          <h2
            id={headingId}
            className={`mt-2 text-2xl font-semibold tracking-tight ${isNormal ? 'text-emerald-800' : 'text-red-800'}`}
          >
            {finding(result.prediction)}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-600">
            {isNormal
              ? 'The model classified this one-second recording as Normal.'
              : `The vibration pattern in this recording was classified as ${result.prediction}.`}
          </p>
        </div>
        <div className={`mt-4 rounded-md border-l-4 px-4 py-3 ${isNormal ? 'border-emerald-600 bg-emerald-50' : 'border-sky-600 bg-sky-50'}`}>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">Suggested next step</p>
          <p className="mt-1 text-sm font-semibold text-slate-900">
            {nextStep(result.prediction)}
          </p>
        </div>
      </div>

      <RailTrackDiagram prediction={result.prediction} />
      <p className="text-xs leading-relaxed text-slate-500">
        This is a model prediction for one recording. It does not establish track safety,
        defect severity or the exact location of a defect.
      </p>
      <RailEvidencePanel evidence={result.evidence} />
      <RailReviewChecklist prediction={result.prediction} checked={entry.review.checkedSteps}
        onChange={(checkedSteps) => onReviewChange({ checkedSteps })} />
      <RailReviewRecord review={entry.review} onChange={onReviewChange} />

      <div className="flex flex-col gap-3 border-t border-slate-200 pt-5">
        <p className="text-xs text-slate-500">
          Submission download: filename and predicted class for this recording.
        </p>
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
        <button type="button" onClick={() => downloadReviewReport(entry)}
          className="rounded-md bg-sky-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-sky-800 focus-visible:outline-2 focus-visible:outline-sky-600">
          Download review report (.html)
        </button>
        <button
          type="button"
          onClick={() => downloadRailPrediction(result)}
          className="shrink-0 rounded-md bg-sky-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-sky-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2"
        >
          Download this prediction (.csv)
        </button>
        </div>
        <p className="text-xs text-slate-500">Open the HTML report in a browser to print or save as PDF. Use the queue's combined export for a batch submission.</p>
      </div>
    </section>
  )
}
