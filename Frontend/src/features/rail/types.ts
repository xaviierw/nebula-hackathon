export type RailLabel = 'Normal' | 'Side I' | 'Side II'

export interface RailPrediction {
  file_id: string
  prediction: RailLabel
}

export interface VibrationMeasurements {
  rms_median: number
  rms_max: number
  abs_peak_max: number
}

export interface RailEvidence {
  samples_per_sensor: number
  column_count: number
  duration_seconds: number
  vibration_sensors_per_side: number
  feature_count: number
  side_i: VibrationMeasurements
  side_ii: VibrationMeasurements
}

export interface RailAnalysis extends RailPrediction {
  evidence: RailEvidence
}

export type ChecklistStep = 'context' | 'evidence' | 'handoff'

export interface RailReview {
  status: 'awaiting_review' | 'reviewed'
  reviewer: string
  runReference: string
  location: string
  notes: string
  checkedSteps: ChecklistStep[]
  updatedAt: string | null
  reviewedAt: string | null
}

export interface RailQueueEntry {
  id: string
  fileName: string
  size: number
  status: 'queued' | 'analysing' | 'done' | 'error'
  analysis: RailAnalysis | null
  analysedAt: string | null
  error: string | null
  excluded: boolean
  review: RailReview
}

export interface RailBatch {
  id: string
  createdAt: string
  entries: RailQueueEntry[]
}

export interface RailWorkspace {
  version: 1
  batches: RailBatch[]
}
