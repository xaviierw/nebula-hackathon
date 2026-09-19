import { emptyReview } from './review.ts'
import type { RailBatch, RailQueueEntry, RailReview, RailWorkspace } from './types'
import { isRailAnalysis, isRecord } from './validation.ts'

export const STORAGE_KEY = 'nebula.rail.workspace.v1'
export const MAX_RAIL_FILE_BYTES = 25 * 1024 * 1024
export const emptyWorkspace = (): RailWorkspace => ({ version: 1, batches: [] })

function isDate(value: unknown): value is string {
  return typeof value === 'string' && Number.isFinite(Date.parse(value))
}

function isReview(value: unknown): value is RailReview {
  if (!isRecord(value)) return false
  return (value.status === 'awaiting_review' || value.status === 'reviewed') &&
    ['reviewer', 'runReference', 'location', 'notes'].every((key) => typeof value[key] === 'string') &&
    Array.isArray(value.checkedSteps) && value.checkedSteps.every((step) => ['context', 'evidence', 'handoff'].includes(step)) &&
    new Set(value.checkedSteps).size === value.checkedSteps.length &&
    (value.updatedAt === null || isDate(value.updatedAt)) &&
    (value.reviewedAt === null || isDate(value.reviewedAt))
}

function isEntry(value: unknown): value is RailQueueEntry {
  if (!isRecord(value) || typeof value.id !== 'string' || typeof value.fileName !== 'string') return false
  if (typeof value.size !== 'number' || !Number.isFinite(value.size) || value.size < 0) return false
  if (!['queued', 'analysing', 'done', 'error'].includes(String(value.status))) return false
  if (typeof value.excluded !== 'boolean' || !isReview(value.review)) return false
  if (value.error !== null && typeof value.error !== 'string') return false
  if (value.status === 'done') {
    return isRailAnalysis(value.analysis) && value.analysis.file_id === value.fileName && isDate(value.analysedAt)
  }
  return value.analysis === null && value.analysedAt === null
}

/** Validate before use, and turn interrupted uploads into explicitly retryable errors. */
export function restoreWorkspace(raw: string): RailWorkspace {
  const value: unknown = JSON.parse(raw)
  if (!isRecord(value) || value.version !== 1 || !Array.isArray(value.batches)) throw new Error('Unsupported saved records')
  const ids = new Set<string>()
  for (const batch of value.batches) {
    if (!isRecord(batch) || typeof batch.id !== 'string' || !isDate(batch.createdAt) || !Array.isArray(batch.entries)) throw new Error('Invalid batch')
    if (ids.has(batch.id)) throw new Error('Duplicate batch')
    ids.add(batch.id)
    const names = new Set<string>()
    for (const entry of batch.entries) {
      if (!isEntry(entry) || ids.has(entry.id) || names.has(entry.fileName.toLowerCase())) throw new Error('Invalid recording')
      ids.add(entry.id)
      names.add(entry.fileName.toLowerCase())
      if (entry.status === 'queued' || entry.status === 'analysing') {
        entry.status = 'error'
        entry.error = 'Upload interrupted. Reselect this recording to retry.'
      }
    }
  }
  return value as unknown as RailWorkspace
}

export function createEntries(files: File[], existing: RailQueueEntry[] = []): RailQueueEntry[] {
  const names = new Set(existing.map((entry) => entry.fileName.toLowerCase()))
  for (const file of files) {
    const key = file.name.toLowerCase()
    if (names.has(key)) throw new Error(`Duplicate filename: ${file.name}. Each filename must be unique within a batch. Start a new batch to analyse it again.`)
    names.add(key)
  }
  return files.map((file) => {
    const error = !file.name.toLowerCase().endsWith('.csv')
      ? 'Expected a sensor recording in CSV format.'
      : file.size > MAX_RAIL_FILE_BYTES ? 'The file exceeds the 25 MiB upload limit.' : null
    return {
      id: crypto.randomUUID(), fileName: file.name, size: file.size,
      status: error ? 'error' : 'queued', error, analysis: null, analysedAt: null,
      excluded: false, review: emptyReview(),
    }
  })
}

export function exportState(batch: RailBatch) {
  const completed = batch.entries.filter((entry) => entry.status === 'done' && !entry.excluded)
  const unresolved = batch.entries.filter((entry) => entry.status !== 'done' && !entry.excluded)
  const excluded = batch.entries.filter((entry) => entry.excluded)
  return { completed, unresolved, excluded, canExport: completed.length > 0 && unresolved.length === 0 }
}
