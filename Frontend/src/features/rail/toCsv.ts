import type { RailPrediction } from './types'
import { downloadText } from './download.ts'

export const RAIL_SUBMISSION_FILENAME = 'rail_predictions.csv'

function csvCell(value: string): string {
  return `"${value.replaceAll('"', '""')}"`
}

export function predictionsCsv(results: RailPrediction[]): string {
  const names = results.map((result) => result.file_id.toLowerCase())
  if (new Set(names).size !== names.length) throw new Error('Submission filenames must be unique.')
  return 'file_id,prediction\r\n' + results.map((result) =>
    `${csvCell(result.file_id)},${csvCell(result.prediction)}\r\n`,
  ).join('')
}

export function downloadRailPredictions(results: RailPrediction[]): void {
  downloadText(predictionsCsv(results), RAIL_SUBMISSION_FILENAME, 'text/csv;charset=utf-8')
}

export function downloadRailPrediction(result: RailPrediction): void {
  downloadRailPredictions([result])
}
