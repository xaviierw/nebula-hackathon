import { apiFetch } from '../../api/client'

export interface ShmPrediction {
  file_id: string
  prediction: number
  observations: number
  weighted_cycle_count: number
  model_id: string
}

export const MAX_FILE_BYTES = 16 * 1024 * 1024
export const MAX_FILES = 32

export async function predictShm(file: File): Promise<ShmPrediction> {
  const body = new FormData()
  body.append('file', file)
  let response: Response
  try {
    response = await apiFetch('/shm/predict', { method: 'POST', body })
  } catch {
    throw new Error('Cannot reach the prediction service. Check that the backend is running, then retry.')
  }
  if (!response.ok) {
    const problem = await response.json().catch(() => null) as { detail?: unknown } | null
    throw new Error(typeof problem?.detail === 'string' ? problem.detail
      : 'The prediction service could not process this recording. Check the backend and retry.')
  }
  const result: ShmPrediction = await response.json()
  if (result.file_id !== file.name || !Number.isFinite(result.prediction) || result.prediction <= 0
      || typeof result.model_id !== 'string') {
    throw new Error('The service returned an invalid prediction. Please retry.')
  }
  return result
}

export function buildShmCsv(results: ShmPrediction[]): string {
  if (!results.length || new Set(results.map(r => r.file_id)).size !== results.length
      || new Set(results.map(r => r.model_id)).size !== 1
      || results.some(r => !Number.isFinite(r.prediction) || r.prediction <= 0)) {
    throw new Error('Predictions must be unique, finite and from the same model.')
  }
  // CSV quoting preserves exact filenames; do not round the submitted predictions.
  const quote = (value: string) => `"${value.replaceAll('"', '""')}"`
  return ['file_id,prediction', ...results.map(r => `${quote(r.file_id)},${r.prediction}`)].join('\r\n') + '\r\n'
}

export function downloadShmCsv(results: ShmPrediction[]) {
  const url = URL.createObjectURL(new Blob([buildShmCsv(results)], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = 'shm_predictions.csv'
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
