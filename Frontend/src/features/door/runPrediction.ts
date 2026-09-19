import { apiFetch } from '../../api/client'
import type { DoorResult } from './types'

interface ApiProblem {
  message?: string
}

async function problemMessage(response: Response): Promise<string> {
  try {
    const problem = (await response.json()) as ApiProblem
    if (typeof problem.message === 'string') return problem.message
  } catch {
    // A proxy may return an HTML error page. Keep the stable fallback.
  }
  return 'Could not analyse that file.'
}

export async function runDoorPrediction(file: File): Promise<DoorResult> {
  const body = new FormData()
  body.append('file', file)

  const response = await apiFetch('/door/predict', {
    method: 'POST',
    body,
  })
  if (!response.ok) throw new Error(await problemMessage(response))

  return (await response.json()) as DoorResult
}
