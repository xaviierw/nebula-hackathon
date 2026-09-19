import { Link } from 'react-router-dom'

import type { Subsystem } from '../subsystems'

/**
 * A card that is a real <Link>, not a <div onClick>. That keeps keyboard focus,
 * middle-click-to-new-tab and screen-reader semantics working for free.
 */
export function SubsystemCard({ subsystem }: { subsystem: Subsystem }) {
  return (
    <Link
      to={subsystem.path}
      className="group block rounded-lg border border-slate-200 bg-white p-5 transition hover:border-sky-400 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
    >
      <h2 className="text-base font-semibold text-slate-900 group-hover:text-sky-700">
        {subsystem.name}
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-slate-600">{subsystem.blurb}</p>
      <span className="mt-4 inline-block text-sm font-medium text-sky-700">Open →</span>
    </Link>
  )
}
