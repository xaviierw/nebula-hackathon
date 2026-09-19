import { downloadText } from './download.ts'
import { finding, nextStep, reviewSteps } from './review.ts'
import type { RailQueueEntry } from './types'

function html(value: string | number): string {
  return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;')
}

export function reviewReport(entry: RailQueueEntry): string {
  if (entry.status !== 'done' || !entry.analysis) throw new Error('A completed prediction is required for a report.')
  const { analysis, review } = entry
  const { prediction, evidence } = analysis
  const normal = prediction === 'Normal'
  const railI = normal ? '#059669' : prediction === 'Side I' ? '#dc2626' : '#64748b'
  const railII = normal ? '#059669' : prediction === 'Side II' ? '#dc2626' : '#64748b'
  const affectedY = prediction === 'Side I' ? 75 : 155
  const measurements = [
    ['Typical vibration strength (median sensor RMS)', evidence.side_i.rms_median, evidence.side_ii.rms_median],
    ['Strongest sensor vibration (maximum RMS)', evidence.side_i.rms_max, evidence.side_ii.rms_max],
    ['Largest acceleration peak (maximum absolute value)', evidence.side_i.abs_peak_max, evidence.side_ii.abs_peak_max],
  ] as const
  const details = [
    ['Record ID', entry.id], ['Source recording', entry.fileName], ['Predicted class', prediction],
    ['Analysed at', entry.analysedAt ?? 'Not recorded'],
    ['Review status', review.status === 'reviewed' ? 'Reviewed' : 'Awaiting review'],
    ['Reviewer', review.reviewer || 'Not provided'], ['Train / run', review.runReference || 'Not provided'],
    ['Track section / location (user supplied)', review.location || 'Not provided'],
    ['Review last edited', review.updatedAt ?? 'Not edited'], ['Marked reviewed at', review.reviewedAt ?? 'Not marked reviewed'],
  ]
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:">
<title>Rail review — ${html(entry.fileName)}</title>
<style>
body{font:15px/1.6 system-ui,sans-serif;color:#0f172a;background:#f8fafc;margin:0}main{max-width:900px;margin:32px auto;padding:32px;background:white}h1{font-size:26px;line-height:1.2}h2{font-size:19px;margin-top:28px}p,dd{overflow-wrap:anywhere}.muted{color:#475569;font-size:13px}.callout{padding:16px;border-left:4px solid #0284c7;background:#f0f9ff}dl{display:grid;grid-template-columns:1fr 2fr;gap:6px 16px}dt{font-weight:600}dd{margin:0;white-space:pre-wrap}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px;border-bottom:1px solid #cbd5e1}th{background:#f1f5f9}.notes{white-space:pre-wrap;padding:16px;background:#f8fafc}svg{display:block;width:100%;height:auto}.checklist li{margin-bottom:12px}section,figure,tr{break-inside:avoid} @media(max-width:550px){main{margin:0;padding:18px}dl{grid-template-columns:1fr}dd{margin-bottom:8px}table{font-size:12px}}@media print{body{background:white}main{padding:0;margin:0;max-width:none}.no-print{display:none}*{print-color-adjust:exact;-webkit-print-color-adjust:exact}}
</style></head><body><main>
<p class="muted">Nebula · Rail Corrugation review report</p>
<h1>${html(finding(prediction))}</h1>
<p class="callout"><strong>Suggested next step:</strong> ${html(nextStep(prediction))}</p>
<p class="no-print muted">This report works offline. Use your browser's Print command to print or save as PDF.</p>
<h2>Recording and review</h2><dl>${details.map(([label, value]) => `<dt>${html(label)}</dt><dd>${html(value)}</dd>`).join('')}</dl>
<figure><svg viewBox="0 0 700 215" role="img" aria-label="${html(finding(prediction))}">
${[150, 225, 300, 375, 450, 525, 600].map((x) => `<rect x="${x}" y="50" width="18" height="130" rx="4" fill="#cbd5e1"/>`).join('')}
<path d="M115 75H665" stroke="${railI}" stroke-width="16" stroke-linecap="round"/>
<path d="M115 155H665" stroke="${railII}" stroke-width="16" stroke-linecap="round"/>
<text x="15" y="82" font-size="22" fill="#0f172a">Side I</text><text x="15" y="162" font-size="22" fill="#0f172a">Side II</text>
${normal ? '' : [190, 245, 300, 355, 410, 465, 520, 575].map((x) => `<path d="M${x - 18} ${affectedY}q9 -13 18 0q9 13 18 0" fill="none" stroke="#450a0a" stroke-width="4"/>`).join('')}
</svg><figcaption class="muted">Schematic viewed from above. Side I: positions 1, 3, 5, 7. Side II: positions 2, 4, 6, 8. Markings do not locate or measure the extent of wear.</figcaption></figure>
<h2>What informed this result?</h2>
<p>The recording passed format checks for ${evidence.column_count} columns and ${evidence.samples_per_sensor.toLocaleString('en')} samples per sensor. Its duration is ${evidence.duration_seconds} second at the dataset's sampling rate. The classifier uses ${evidence.feature_count} inputs summarising vibration strength, spikes and side-to-side differences from ${evidence.vibration_sensors_per_side} vibration sensors on each side.</p>
<table><thead><tr><th>Measurement</th><th>Side I (m/s²)</th><th>Side II (m/s²)</th></tr></thead><tbody>
${measurements.map(([label, left, right]) => `<tr><td>${html(label)}</td><td>${left.toPrecision(6)}</td><td>${right.toPrecision(6)}</td></tr>`).join('')}
</tbody></table><p class="muted">These are measured inputs, not individual feature contributions or defect severity. Higher vibration alone does not determine the class. RMS summarises vibration strength over the recording; m/s² is a unit of acceleration.</p>
<h2>Review checklist</h2><ul class="checklist">${reviewSteps(prediction).map((step) => `<li><strong>${review.checkedSteps.includes(step.id) ? '[Checked]' : '[Not checked]'} ${html(step.title)}</strong><br>${html(step.description)}</li>`).join('')}</ul>
<h2>Review notes</h2><p class="notes">${html(review.notes || 'No notes provided.')}</p>
<p class="muted">This is a model prediction for one recording. It does not establish track safety, defect severity or exact defect location. Review status and checklist selections document preparation and review, not an inspection, repair or dispatched maintenance request.</p>
<p class="muted">Report exported ${html(new Date().toISOString())}. Source records are stored in the originating browser; this download is a snapshot.</p>
</main></body></html>`
}

export function downloadReviewReport(entry: RailQueueEntry): void {
  const stem = entry.fileName.replace(/\.csv$/i, '').replace(/[^a-zA-Z0-9_-]/g, '_') || 'recording'
  downloadText(reviewReport(entry), `${stem}_rail_review.html`, 'text/html;charset=utf-8')
}
