import type { DoorDetailRow } from '../types'

/**
 * How much current this cycle drew, against the limit it was judged on.
 *
 * The threshold sits at the halfway mark, so the bar is scaled to twice the
 * limit and clamped there. That fixed anchor is what makes rows comparable at a
 * glance even though Open (304 mA) and Close (251 mA) are judged differently:
 * the line is always in the same place, and "past it" always looks the same.
 *
 * Note what this is NOT: a confidence meter. It is two measured numbers and the
 * gap between them. margin_ratio would be the more "model-native" thing to plot,
 * but it is a distance in training-gap units, which means nothing to a reader,
 * and rendering it as a percentage would invent a probability the model never
 * produced.
 */

const THRESHOLD_POSITION_PERCENT = 50

export function CurrentBar({ row }: { row: DoorDetailRow }) {
  const isFlagged = row.prediction === 'Abnormal resistance'
  const fillPercent = Math.min(row.steady_current_mA / (row.threshold_mA * 2), 1) * 100

  return (
    <div>
      <div className="relative h-2 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className={['h-full rounded-full', isFlagged ? 'bg-red-500' : 'bg-emerald-500'].join(' ')}
          style={{ width: fillPercent + '%' }}
        />
        <div
          aria-hidden="true"
          className="absolute inset-y-0 w-px bg-slate-400"
          style={{ left: THRESHOLD_POSITION_PERCENT + '%' }}
        />
      </div>

      <p className="mt-1.5 text-xs text-slate-500">
        <span className="font-medium text-slate-900">
          {row.steady_current_mA.toFixed(0)} mA
        </span>
        {' against a '}
        {row.threshold_mA.toFixed(0)} mA limit
      </p>
    </div>
  )
}
