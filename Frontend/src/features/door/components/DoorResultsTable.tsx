import { describeMargin, severityOf, sortByConcern } from '../describe'
import { formatClockMs, formatDuration } from '../formatTime'
import type { DoorDetailRow } from '../types'
import { CurrentBar } from './CurrentBar'

/**
 * One row per door cycle, flagged ones first and worst at the top.
 *
 * Identified by timestamp and nothing else. The headers documentation lists
 * Car Type, Car Number and Door Number, but the audit found none of the three
 * is present in the delivered files - "absent, not constant" - so there is no
 * honest way to say which door this was.
 *
 * On a narrow screen the table scrolls horizontally rather than reflowing: the
 * current bar needs its width to stay readable, and a stacked card layout would
 * make 38 rows far harder to scan.
 */
export function DoorResultsTable({ detail }: { detail: DoorDetailRow[] }) {
  const rows = sortByConcern(detail)

  return (
    <section className="overflow-hidden rounded-lg border border-slate-200 bg-white">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[40rem] text-left text-sm">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr className="text-xs font-medium uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-5 py-3">
                Time
              </th>
              <th scope="col" className="px-5 py-3">
                Operation
              </th>
              <th scope="col" className="px-5 py-3 w-64">
                Motor current
              </th>
              <th scope="col" className="px-5 py-3">
                Verdict
              </th>
            </tr>
          </thead>

          <tbody className="divide-y divide-slate-100">
            {rows.map((row) => {
              const severity = severityOf(row)
              const isFlagged = row.prediction === 'Abnormal resistance'

              return (
                <tr key={row.start_time} className={isFlagged ? 'bg-red-50/40' : undefined}>
                  <td className="px-5 py-3 align-top">
                    <div className="font-medium tabular-nums text-slate-900">
                      {formatClockMs(row.start_time)}
                    </div>
                    <div className="mt-0.5 text-xs text-slate-500">
                      {formatDuration(row.start_time, row.end_time)}
                    </div>
                  </td>

                  <td className="px-5 py-3 align-top text-slate-700">{row.operation}</td>

                  <td className="px-5 py-3 align-top">
                    <CurrentBar row={row} />
                  </td>

                  <td className="px-5 py-3 align-top">
                    <VerdictBadge isFlagged={isFlagged} severe={severity === 'severe'} />
                    <div
                      className={[
                        'mt-1 text-xs',
                        isFlagged ? 'font-medium text-red-700' : 'text-slate-500',
                      ].join(' ')}
                    >
                      {describeMargin(row)}
                    </div>
                    {severity === 'borderline' && (
                      <div className="mt-1 text-xs text-amber-700">
                        higher than any cycle in training
                      </div>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function VerdictBadge({ isFlagged, severe }: { isFlagged: boolean; severe: boolean }) {
  if (!isFlagged) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700">
        <span aria-hidden="true">✓</span> Normal
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-semibold text-red-800">
      <span aria-hidden="true">⚑</span> {severe ? 'Flagged — severe' : 'Flagged'}
    </span>
  )
}
