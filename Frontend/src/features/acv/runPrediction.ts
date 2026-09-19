import { apiFetch } from '../../api/client'
import type { AcvBatchResult } from './types'

export async function runAcvPrediction(file: File): Promise<AcvBatchResult> {
  const body = new FormData()
  body.append('files', file)
  return requestBatch(body)
}

async function requestBatch(body: FormData): Promise<AcvBatchResult> {
  const response = await apiFetch('/acv/predict-batch', {
    method: 'POST',
    body,
  })

  if (!response.ok) {
    const problem = (await response.json().catch(() => null)) as { message?: string } | null
    throw new Error(problem?.message ?? 'Could not analyse that file.')
  }

  return (await response.json()) as AcvBatchResult
}