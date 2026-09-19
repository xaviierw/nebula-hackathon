import { Link } from 'react-router-dom'

import { SUBSYSTEMS } from '../subsystems'
import type { SubsystemId } from '../subsystems'

/**
 * Stand-in body for a subsystem page that has no logic yet.
 *
 * Each subsystem keeps its own page file so four people can work in parallel
 * without colliding; this just saves repeating the same empty markup four
 * times. Replace the <SubsystemPlaceholder /> call in a page with the real
 * upload and results UI when that subsystem is ready.
 */
export function SubsystemPlaceholder({ id }: { id: SubsystemId }) {
  const subsystem = SUBSYSTEMS.find((candidate) => candidate.id === id)!

  return (
    <>
      <Link to="/home" className="text-sm font-medium text-sky-700 hover:text-sky-800">
        ← Back to dashboard
      </Link>

      <h1 className="mt-6 text-2xl font-semibold tracking-tight text-slate-900">
        {subsystem.name}
      </h1>
      <p className="mt-2 text-sm text-slate-600">{subsystem.blurb}</p>

      <div className="mt-8 rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center">
        <p className="text-sm text-slate-500">Not implemented yet.</p>
      </div>
    </>
  )
}
