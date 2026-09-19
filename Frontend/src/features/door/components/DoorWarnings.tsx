import type { DoorWarning } from '../types'

/**
 * Notes the backend attached to this file.
 *
 * Warnings never block a result - predict.py is explicit that "the caller gets
 * the result AND the caveat" - so these sit beside the table rather than
 * replacing it.
 *
 * Both severities are rendered. That matters more than it looks: the current
 * sample emits only `info` warnings, so a panel that filtered for
 * severity === 'warning' would silently show nothing at all.
 *
 * Messages are printed verbatim. They are written on the Python side for a
 * non-technical reader, and rewording them here would only let the two drift.
 */
export function DoorWarnings({ warnings }: { warnings: DoorWarning[] }) {
  if (warnings.length === 0) return null

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900">Notes about this file</h2>

      <ul className="mt-3 space-y-3">
        {warnings.map((warning, index) => {
          const isWarning = warning.severity === 'warning'
          return (
            <li
              key={warning.code + '-' + index}
              className={[
                'flex items-start gap-3 rounded-md border px-3 py-2.5',
                isWarning ? 'border-amber-200 bg-amber-50' : 'border-slate-200 bg-slate-50',
              ].join(' ')}
            >
              <span
                aria-hidden="true"
                className={[
                  'text-sm leading-relaxed',
                  isWarning ? 'text-amber-600' : 'text-slate-400',
                ].join(' ')}
              >
                {isWarning ? '⚠' : 'ℹ'}
              </span>
              <p className="text-sm leading-relaxed text-slate-700">{warning.message}</p>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
