/**
 * Turning model output into sentences, without overstating it.
 *
 * Everything here is derived from two measured currents, so a reader can check
 * the arithmetic. None of it is a probability. The model does not produce one,
 * and margin_ratio - which looks like it might - is a distance expressed in
 * training-gap units, which would be meaningless dressed up as a percentage.
 */

import type { DoorDetailRow } from './types'

/** "96% over the limit" / "22% under the limit". */
export function describeMargin(row: DoorDetailRow): string {
  const ratio = row.steady_current_mA / row.threshold_mA - 1
  const percent = Math.abs(Math.round(ratio * 100))
  return ratio >= 0 ? percent + '% over the limit' : percent + '% under the limit'
}

/**
 * A coarse band, used only for ordering and emphasis.
 *
 * margin_ratio is in multiples of the headroom between the threshold and the
 * worst healthy cycle in training. -1.0 is therefore the meaningful anchor:
 * at -1 this cycle drew exactly as much as the worst healthy cycle seen.
 * Between -1 and 0 a cycle passes, but draws more than anything in training
 * did - genuinely borderline, and worth marking even though nothing in the
 * current sample lands there.
 */
export type DoorSeverity = 'severe' | 'flagged' | 'borderline' | 'normal'

export function severityOf(row: DoorDetailRow): DoorSeverity {
  if (row.prediction === 'Abnormal resistance') {
    return row.margin_ratio >= 5 ? 'severe' : 'flagged'
  }
  return row.margin_ratio > -1 ? 'borderline' : 'normal'
}

/** Flagged first, worst at the top; normal cycles keep their chronological order. */
export function sortByConcern(detail: DoorDetailRow[]): DoorDetailRow[] {
  return [...detail].sort((a, b) => {
    const aFlagged = a.prediction === 'Abnormal resistance'
    const bFlagged = b.prediction === 'Abnormal resistance'
    if (aFlagged !== bFlagged) return aFlagged ? -1 : 1
    if (aFlagged) return b.margin_ratio - a.margin_ratio
    return 0
  })
}
