import { formatSpan } from '../formatTime'
import type { DoorDetailRow } from '../types'

/**
 * The headline. This is the product story in one line: a recording of thousands
 * of rows nobody would read becomes a handful of verdicts and a shortlist of
 * timestamps to go and inspect.
 *
 * Note what is absent: no accuracy figure, and no timeline. The gaps between
 * cycles in these recordings are elided cycles rather than idle time - the audit
 * is explicit that "any model that reads meaning into gap duration is modelling
 * the curation, not the door" - so drawing a to-scale timeline would invent
 * quiet periods that never happened.
 */
export function DoorSummary({ detail }: { detail: DoorDetailRow[] }) {
  const flagged = detail.filter((row) => row.prediction === 'Abnormal resistance').length
  const normal = detail.length - flagged
  const span = formatSpan(detail[0].start_time, detail[detail.length - 1].end_time)

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
        <Stat value={detail.length} label="cycles found" />
        <Stat value={normal} label="normal" tone="normal" />
        <Stat value={flagged} label="flagged" tone={flagged > 0 ? 'flagged' : 'normal'} />
        <span className="text-sm text-slate-500">over {span} of recording</span>
      </div>

      {flagged > 0 && (
        <p className="mt-4 border-t border-slate-100 pt-3 text-sm text-slate-600">
          {flagged === 1 ? 'One cycle drew' : flagged + ' cycles drew'} more current than a healthy
          door needs. Each one is timestamped below — that is the moment to inspect.
        </p>
      )}
    </section>
  )
}

function Stat({
  value,
  label,
  tone = 'neutral',
}: {
  value: number
  label: string
  tone?: 'neutral' | 'normal' | 'flagged'
}) {
  const colour =
    tone === 'flagged' ? 'text-red-600' : tone === 'normal' ? 'text-emerald-600' : 'text-slate-900'

  return (
    <span className="flex items-baseline gap-1.5">
      <span className={['text-2xl font-semibold tabular-nums', colour].join(' ')}>{value}</span>
      <span className="text-sm text-slate-600">{label}</span>
    </span>
  )
}
