import type { AcvBatchResult } from './types'

export const ACV_SUBMISSION_FILENAME = 'acv_predictions.csv'

function escapeCsv(value: string): string {
  return /[",\n]/.test(value) ? `"${value.replaceAll('"', '""')}"` : value
}

export function downloadAcvPredictionsCsv(batch: AcvBatchResult): void {
  const rows = batch.results
    .filter((item) => item.ok && item.result !== null)
    .map((item) => [item.filename, item.result!.ranked_cars.join('|')])

  const csv = '\ufeff' + [
    'file_id,ranked_cars',
    ...rows.map(([fileId, rankedCars]) => `${escapeCsv(fileId)},${escapeCsv(rankedCars)}`),
  ].join('\r\n')

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = ACV_SUBMISSION_FILENAME
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}