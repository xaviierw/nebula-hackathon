/**
 * Mirrors what the Door pipeline's `predict_stream()` returns, so that swapping
 * the placeholder in runPrediction.ts for a real API call is type-safe and
 * touches nothing else.
 *
 * Source of truth: Backend/Door/prediction/predict.py and core/classifier.py.
 */

/**
 * The two labels, spelled exactly as the scorer expects.
 *
 * "Abnormal resistance" - lowercase r, one space, never "Abnormal" alone.
 * verify_submission.py rejects anything else, and a mislabelled segment scores
 * zero even with perfect timing. Typed as a union so the compiler enforces it.
 */
export type DoorPrediction = 'Normal' | 'Abnormal resistance'

export type DoorOperation = 'Open' | 'Close'

export interface DoorDetailRow {
  /** Native format, e.g. "2023-7-5-0-22-38-967". Not Date-parseable - see formatTime.ts. */
  start_time: string
  end_time: string
  /** Inclusive row indices into the uploaded CSV, carried so a caller can slice the waveform. */
  start_row: number
  end_row: number
  operation: DoorOperation
  /** Mean motor current across mid-travel (20%-85% of the leaf's own stroke). */
  steady_current_mA: number
  /** The fitted limit for this operation: 304.2 mA for Open, 251.3 mA for Close. */
  threshold_mA: number
  prediction: DoorPrediction
  /**
   * (current - threshold) / training gap. The SIGN is the verdict and never
   * disagrees with `prediction`; the magnitude is distance past the line.
   *
   * This is NOT a probability. Do not render it as a confidence percentage.
   * -1.0 is the one meaningful anchor: drew exactly as much as the worst healthy
   * cycle seen in training.
   */
  margin_ratio: number
}

export interface DoorWarning {
  code: 'sampling_interval' | 'segment_duration'
  severity: 'warning' | 'info'
  /** Already written for a non-technical reader by the backend - render verbatim. */
  message: string
  [extra: string]: unknown
}

export interface DoorResult {
  detail: DoorDetailRow[]
  warnings: DoorWarning[]
}
