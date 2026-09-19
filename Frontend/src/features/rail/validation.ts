import type { RailAnalysis } from './types'

export function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function isNonnegativeNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0
}

export function isRailAnalysis(value: unknown): value is RailAnalysis {
  if (!isRecord(value) || typeof value.file_id !== 'string') return false
  if (value.prediction !== 'Normal' && value.prediction !== 'Side I' && value.prediction !== 'Side II') return false
  const evidence = value.evidence
  if (!isRecord(evidence)) return false
  for (const key of ['samples_per_sensor', 'column_count', 'duration_seconds', 'vibration_sensors_per_side', 'feature_count']) {
    if (!isNonnegativeNumber(evidence[key]) || evidence[key] === 0) return false
  }
  for (const side of ['side_i', 'side_ii']) {
    const measurements = evidence[side]
    if (!isRecord(measurements)) return false
    for (const metric of ['rms_median', 'rms_max', 'abs_peak_max']) {
      if (!isNonnegativeNumber(measurements[metric])) return false
    }
  }
  return true
}
