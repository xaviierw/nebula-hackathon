export interface AcvWarning {
  code: string
  severity: 'warning' | 'info'
  message: string
}

export interface AcvResult {
  ranked_cars: string[]
  scores: Record<string, number>
  warnings: AcvWarning[]
}

export interface AcvBatchItem {
  filename: string
  ok: boolean
  skipped?: boolean
  result: AcvResult | null
  message: string | null
}

export interface AcvBatchResult {
  results: AcvBatchItem[]
}