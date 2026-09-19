import { apiFetch } from '../../api/client'
import type { RailAnalysis } from './types'
import { isRailAnalysis, isRecord } from './validation'

interface ApiProblem {
  message?: string
}

interface BatchItem {
  filename: string
  ok: boolean
  result: unknown
  message: string | null
}

export type RailPredictionOutcome =
  | { ok: true; analysis: RailAnalysis }
  | { ok: false; filename: string; message: string }

async function problemMessage(response: Response): Promise<string> {
  try {
    const problem = (await response.json()) as ApiProblem
    if (typeof problem.message === 'string') return problem.message
  } catch {
    // A proxy may return an HTML error page. Use the stable fallback below.
  }
  return 'Could not analyse the selected recording(s).'
}

function analysisFor(filename: string, payload: unknown): RailAnalysis | null {
  const candidate = isRecord(payload) ? { ...payload, file_id: filename } : payload
  return isRailAnalysis(candidate) ? candidate : null
}

/** One-file helper retained for retries and focused component tests. */
export async function runRailPrediction(file: File, signal?: AbortSignal): Promise<RailAnalysis> {
  const body = new FormData()
  body.append('file', file)

  const response = await apiFetch('/rail-corrugation/predict', { method: 'POST', body, signal })
  if (!response.ok) throw new Error(await problemMessage(response))

  const result = analysisFor(file.name, await response.json())
  if (!result) throw new Error('The analysis response is incomplete. Please try again.')
  return result
}

/** Use the shared backend's per-file-error batch contract for a queue upload. */
export async function runRailPredictionBatch(
  files: File[], signal?: AbortSignal,
): Promise<RailPredictionOutcome[]> {
  const body = new FormData()
  files.forEach((file) => body.append('files', file))

  const response = await apiFetch('/rail-corrugation/predict-batch', {
    method: 'POST', body, signal,
  })
  if (!response.ok) throw new Error(await problemMessage(response))

  const payload: unknown = await response.json()
  if (!isRecord(payload) || !Array.isArray(payload.results) || payload.results.length !== files.length) {
    throw new Error('The batch response is incomplete. Please try again.')
  }

  return payload.results.map((value, index): RailPredictionOutcome => {
    const item = value as Partial<BatchItem>
    const expectedName = files[index].name
    if (!isRecord(value) || item.filename !== expectedName || typeof item.ok !== 'boolean') {
      throw new Error('The batch response does not match the uploaded files. Please try again.')
    }
    if (!item.ok) {
      return {
        ok: false,
        filename: expectedName,
        message: typeof item.message === 'string' ? item.message : 'Analysis failed. Please retry.',
      }
    }
    const analysis = analysisFor(expectedName, item.result)
    if (!analysis) throw new Error(`The analysis response for ${expectedName} is incomplete.`)
    return { ok: true, analysis }
  })
}
