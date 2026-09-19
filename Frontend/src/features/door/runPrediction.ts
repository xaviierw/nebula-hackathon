/**
 * ==========================================================================
 *  THE BACKEND SEAM. This is the only file that talks to the Door API.
 * ==========================================================================
 *
 * The path is relative, so the request is same-origin in dev (Vite proxies
 * /api to 127.0.0.1:8000 -- see vite.config.ts) and in production (a host-level
 * rewrite). CORS therefore never enters the picture.
 *
 * The response shape is not converted or renamed on the way in: DoorResult in
 * types.ts mirrors what the backend's _rows() emits, field for field, in
 * snake_case. Camelizing here would mean two names for every column and a
 * mapping layer to keep in sync with the model.
 */

import { apiFetch } from '../../api/client'
import type { DoorResult } from './types'

/**
 * Every error response from this API is `{"message": "..."}` -- never
 * FastAPI's default `{"detail": ...}`, which would collide with the `detail`
 * field on a successful Door body. See Backend/app/errors.py.
 */
interface ApiProblem {
  message?: string
}

const GENERIC_FAILURE = 'Could not analyse that file.'

export async function runDoorPrediction(file: File): Promise<DoorResult> {
  const body = new FormData()
  // The field name is part of the contract; the backend declares
  // `file: UploadFile = File(...)` and rejects anything else with a 422.
  body.append('file', file)

  let response: Response
  try {
    response = await apiFetch('/door/predict', { method: 'POST', body })
  } catch {
    // fetch() only rejects on a transport failure, never on an HTTP error
    // status. In practice during development this means the API is not
    // running, which is worth saying plainly rather than surfacing the
    // browser's "Failed to fetch".
    throw new Error(
      'Could not reach the server.\n' +
        'Check that the backend is running on http://127.0.0.1:8000.',
    )
  }

  if (!response.ok) {
    // The Python side raises DoorInputError / DoorModelError, whose messages
    // are written for a non-technical reader and safe to show verbatim.
    // Anything else arrives as a generic message from the 500 handler, which
    // is also safe -- it never echoes an exception string.
    throw new Error(await readProblem(response))
  }

  return (await response.json()) as DoorResult
}

/**
 * Pull the message off an error response.
 *
 * Guarded because not every non-2xx response comes from the API itself: the
 * Vite proxy answers with HTML when it cannot reach the backend, and .json()
 * would throw on that, replacing a useful status with a parse error.
 */
async function readProblem(response: Response): Promise<string> {
  try {
    const problem = (await response.json()) as ApiProblem
    return problem.message ?? GENERIC_FAILURE
  } catch {
    return `${GENERIC_FAILURE} (server responded ${response.status})`
  }
}

/**
 * Whether the page is showing canned data. Drives the demo banner in
 * DoorPage. Now false: the results above come from the real model.
 */
export const IS_PLACEHOLDER_DATA = false
