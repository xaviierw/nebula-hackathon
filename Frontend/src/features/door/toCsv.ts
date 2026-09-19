/**
 * Builds the graded submission file in the browser. No backend involved.
 *
 * The rules come from Backend/Door/prediction/verify_submission.py, which
 * actually checks them, so they are not negotiable:
 *
 *   - the filename must be exactly `door_predictions.csv`
 *   - exactly three columns, in this order: start_time,end_time,prediction
 *   - NO file_id column: Test.csv is one continuous stream, not per-file records
 *
 * The page shows more than this (current, threshold, how far past the limit),
 * and the spec does permit an extra `confidence` column - but the graded file
 * stays identical in shape to 04_Example_Submission/door_predictions.csv.
 * A richer export belongs behind its own separate button.
 */

import type { DoorDetailRow } from './types'

export const SUBMISSION_FILENAME = 'door_predictions.csv'

export function buildPredictionsCsv(detail: DoorDetailRow[]): string {
  const lines = ['start_time,end_time,prediction']
  for (const row of detail) {
    lines.push([row.start_time, row.end_time, row.prediction].join(','))
  }
  return lines.join('\n') + '\n'
}

/** Triggers a browser download. Nothing leaves the machine. */
export function downloadPredictionsCsv(detail: DoorDetailRow[]): void {
  const blob = new Blob([buildPredictionsCsv(detail)], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)

  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = SUBMISSION_FILENAME
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)

  URL.revokeObjectURL(url)
}
