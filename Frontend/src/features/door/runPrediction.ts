/**
 * ==========================================================================
 *  THE BACKEND SEAM. This is the only file that changes when the API lands.
 * ==========================================================================
 *
 * There is no API yet, so this returns canned data after a short delay. The
 * delay is not decoration: it makes the page exercise its real loading state
 * rather than snapping straight to results.
 *
 * When Backend/Door is wrapped in FastAPI, replace the body with the block
 * quoted below. Nothing else on the page needs to change, because DoorResult
 * already mirrors what predict_stream() returns.
 */

import { DOOR_FIXTURE } from './fixture'
import type { DoorResult } from './types'

const FAKE_LATENCY_MS = 900

/**
 * The real implementation, kept here so the swap is mechanical:
 *
 *   import { apiFetch } from '../../api/client'
 *
 *   export async function runDoorPrediction(file: File): Promise<DoorResult> {
 *     const body = new FormData()
 *     body.append('file', file)
 *
 *     const response = await apiFetch('/door/predict', { method: 'POST', body })
 *     if (!response.ok) {
 *       // The Python side raises DoorInputError / DoorModelError, whose messages
 *       // are written for a non-technical reader and safe to show verbatim.
 *       const problem = (await response.json()) as { message?: string }
 *       throw new Error(problem.message ?? 'Could not analyse that file.')
 *     }
 *     return (await response.json()) as DoorResult
 *   }
 */
export async function runDoorPrediction(file: File): Promise<DoorResult> {
  // Deliberately unused: nothing reads the file until the API exists.
  void file
  await new Promise((resolve) => setTimeout(resolve, FAKE_LATENCY_MS))
  return DOOR_FIXTURE
}

/** Whether the page is showing canned data. Drives the demo banner. */
export const IS_PLACEHOLDER_DATA = true
