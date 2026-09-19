import assert from 'node:assert/strict'
import { test } from 'node:test'

import { emptyReview } from '../src/features/rail/review.ts'
import { reviewReport } from '../src/features/rail/report.ts'
import { predictionsCsv } from '../src/features/rail/toCsv.ts'
import { createEntries, exportState, restoreWorkspace } from '../src/features/rail/workspace.ts'
import type { RailAnalysis, RailBatch, RailQueueEntry } from '../src/features/rail/types.ts'

const analysis: RailAnalysis = {
  file_id: 'Test1.csv', prediction: 'Side I', evidence: {
    samples_per_sensor: 10000, column_count: 129, duration_seconds: 1,
    vibration_sensors_per_side: 32, feature_count: 15,
    side_i: { rms_median: 1, rms_max: 2, abs_peak_max: 3 },
    side_ii: { rms_median: 0.5, rms_max: 1, abs_peak_max: 2 },
  },
}
function completed(): RailQueueEntry {
  return {
    id: 'entry-1', fileName: 'Test1.csv', size: 1234, status: 'done', analysis,
    analysedAt: '2026-09-19T02:00:00Z', error: null, excluded: false,
    review: { ...emptyReview(), notes: 'Inspect related recordings', reviewer: 'Billy',
      checkedSteps: ['context'], status: 'reviewed', updatedAt: '2026-09-19T02:01:00Z', reviewedAt: '2026-09-19T02:01:00Z' },
  }
}
function batch(entries: RailQueueEntry[]): RailBatch {
  return { id: 'batch-1', createdAt: '2026-09-19T01:00:00Z', entries }
}

test('saved records preserve the result, evidence, review, notes and checklist across restoration', () => {
  const saved = { version: 1, batches: [batch([completed()])] }
  assert.deepEqual(restoreWorkspace(JSON.stringify(saved)), saved)
})

test('interrupted queue entries become failures without losing completed reviews', () => {
  const queued = createEntries([new File(['x'], 'Test2.csv')])[0]
  queued.status = 'analysing'
  const saved = restoreWorkspace(JSON.stringify({ version: 1, batches: [batch([completed(), queued])] }))
  assert.equal(saved.batches[0].entries[1].status, 'error')
  assert.match(saved.batches[0].entries[1].error!, /interrupted/)
  assert.deepEqual(saved.batches[0].entries[0], completed())
})

test('malformed or contradictory saved records are rejected', () => {
  assert.throws(() => restoreWorkspace('{broken'))
  assert.throws(() => restoreWorkspace('{"version":2,"batches":[]}'))
  const bad = completed()
  bad.fileName = 'wrong.csv'
  assert.throws(() => restoreWorkspace(JSON.stringify({ version: 1, batches: [batch([bad])] })))
  assert.throws(() => restoreWorkspace(JSON.stringify({ version: 1, batches: [batch([completed(), completed()])] })))
})

test('duplicate names are rejected both within an upload and across the current batch', () => {
  assert.throws(() => createEntries([new File(['a'], 'Test.csv'), new File(['b'], 'test.CSV')]), /Duplicate filename/)
  assert.throws(() => createEntries([new File(['a'], 'TEST1.csv')], [completed()]), /Duplicate filename/)
})

test('invalid file types remain visible as failed queue entries', () => {
  const entries = createEntries([new File(['x'], 'bad.txt'), new File(['x'], 'good.CSV')])
  assert.equal(entries[0].status, 'error')
  assert.equal(entries[0].analysis, null)
  assert.equal(entries[1].status, 'queued')
})

test('combined export blocks unresolved files until explicitly excluded', () => {
  const failed = createEntries([new File(['x'], 'bad.txt')])[0]
  const current = batch([completed(), failed])
  assert.equal(exportState(current).canExport, false)
  failed.excluded = true
  assert.equal(exportState(current).canExport, true)
  assert.equal(exportState(current).excluded.length, 1)
  assert.equal(exportState(current).completed.length, 1)
  assert.equal(exportState(batch([failed])).canExport, false)
})

test('submission CSV preserves upload order, quotes filenames and has exactly the two required fields', () => {
  assert.equal(predictionsCsv([
    { file_id: 'second,"recording".csv', prediction: 'Side II' },
    { file_id: 'first.csv', prediction: 'Normal' },
  ]), 'file_id,prediction\r\n"second,""recording"".csv","Side II"\r\n"first.csv","Normal"\r\n')
  assert.throws(() => predictionsCsv([analysis, analysis]), /unique/)
})

test('downloadable report includes measured evidence and saved review context, escaping user HTML', () => {
  const entry = completed()
  entry.review.notes = '<script>alert("notes")</script> & <img src=x onerror=alert(1)>'
  entry.review.location = '<Main line>'
  const report = reviewReport(entry)
  assert.match(report, /Possible corrugation on Side I/)
  assert.match(report, /<svg/)
  assert.match(report, /Billy/)
  assert.match(report, /\[Checked\] Confirm the recording context/)
  assert.match(report, /1.00000/)
  assert.match(report, /&lt;Main line&gt;/)
  assert.match(report, /&lt;script&gt;/)
  assert.doesNotMatch(report, /<script>|<img src=x/)
  assert.match(report, /Reviewed/)
})
