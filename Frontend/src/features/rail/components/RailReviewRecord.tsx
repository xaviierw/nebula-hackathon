import { useId } from 'react'

import type { RailReview } from '../types'

const inputClass = 'mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-500'

export function RailReviewRecord({ review, onChange }: {
  review: RailReview
  onChange: (patch: Partial<RailReview>) => void
}) {
  const id = useId()
  const reviewed = review.status === 'reviewed'
  return (
    <section className="rounded-lg border border-slate-200 p-5" aria-labelledby={`${id}-heading`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 id={`${id}-heading`} className="text-base font-semibold text-slate-900">Review record</h3>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${reviewed ? 'bg-sky-100 text-sky-900' : 'bg-slate-100 text-slate-700'}`}>
          {reviewed ? 'Reviewed' : 'Awaiting review'}
        </span>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-slate-500">
        Add the recording context and your observations. Changes are saved in this browser;
        the report includes these notes and the checklist.
      </p>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <label className="text-sm font-medium text-slate-700" htmlFor={`${id}-reviewer`}>
          Reviewer
          <input id={`${id}-reviewer`} name="reviewer" className={inputClass} maxLength={200} value={review.reviewer}
            onChange={(event) => onChange({ reviewer: event.target.value })} placeholder="Name or team" />
        </label>
        <label className="text-sm font-medium text-slate-700" htmlFor={`${id}-run`}>
          Train / run reference
          <input id={`${id}-run`} name="runReference" className={inputClass} maxLength={300} value={review.runReference}
            onChange={(event) => onChange({ runReference: event.target.value })} placeholder="From your recording records" />
        </label>
        <label className="text-sm font-medium text-slate-700 sm:col-span-2" htmlFor={`${id}-location`}>
          Track section / location
          <input id={`${id}-location`} name="location" className={inputClass} maxLength={500} value={review.location}
            onChange={(event) => onChange({ location: event.target.value })} placeholder="Enter if known; not inferred by the model" />
        </label>
        <label className="text-sm font-medium text-slate-700 sm:col-span-2" htmlFor={`${id}-notes`}>
          Review notes
          <textarea id={`${id}-notes`} name="notes" className={inputClass} rows={4} maxLength={10000} value={review.notes}
            onChange={(event) => onChange({ notes: event.target.value })} placeholder="Observations, related recordings and proposed follow-up" />
        </label>
      </div>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-slate-500">
          {review.updatedAt ? `Last edited ${new Date(review.updatedAt).toLocaleString()}` : 'No review edits yet.'}
        </p>
        <button type="button" className="rounded-md border border-sky-700 px-3 py-2 text-sm font-semibold text-sky-800 hover:bg-sky-50 focus-visible:outline-2 focus-visible:outline-sky-600"
          onClick={() => onChange({ status: reviewed ? 'awaiting_review' : 'reviewed', reviewedAt: reviewed ? null : new Date().toISOString() })}>
          {reviewed ? 'Reopen review' : 'Mark reviewed'}
        </button>
      </div>
      <p className="mt-3 text-xs text-slate-500">Reviewed records document a human review of this result, not completion of an inspection or repair.</p>
    </section>
  )
}
