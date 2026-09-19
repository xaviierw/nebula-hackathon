import { apiFetch } from '../../api/client'
import type { RailAnalysis } from './types'
import { isRailAnalysis } from './validation'

interface ApiProblem {
  detail?: string
  message?: string
}

export async function runRailPrediction(file: File, signal?: AbortSignal): Promise<RailAnalysis> {
  const body = new FormData()
  body.append('file', file)

  const response = await apiFetch('/rail-corrugation/predict', {
    method: 'POST',
    body,
    signal,
  })

  if (!response.ok) {
    let message = 'Could not analyse that file.'
    try {
      const problem = (await response.json()) as ApiProblem
      if (typeof problem.detail === 'string') message = problem.detail
      else if (typeof problem.message === 'string') message = problem.message
    } catch {
      // Keep the generic message when a proxy or server returns non-JSON.
    }
    throw new Error(message)
  }

  const result: unknown = await response.json()
  if (!isRailAnalysis(result) || result.file_id !== file.name) {
    throw new Error('The analysis response is incomplete. Please try again.')
  }
  return result
}
