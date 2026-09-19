/**
 * The four subsystems, declared once.
 *
 * They appear both as cards on the dashboard and as routes in App.tsx. Keeping
 * a single source of truth stops the two drifting apart as the pages get built
 * out. `id` doubles as the URL slug, so display names can change freely without
 * breaking links.
 */

export type SubsystemId = 'door' | 'acv' | 'rail-corrugation' | 'shm'

export interface Subsystem {
  id: SubsystemId
  /** Display name, shown on the card and as the page heading. */
  name: string
  /** One line describing what the subsystem does. */
  blurb: string
  /** Route path, always `/subsystem/${id}`. */
  path: string
}

export const SUBSYSTEMS: Subsystem[] = [
  {
    id: 'door',
    name: 'Door',
    blurb: 'Detect and classify door open/close cycles in a continuous current stream.',
    path: '/subsystem/door',
  },
  {
    id: 'acv',
    name: 'ACV',
    blurb: 'Rank train cars by how likely their air-conditioning is to be faulty.',
    path: '/subsystem/acv',
  },
  {
    id: 'rail-corrugation',
    name: 'Rail Corrugation',
    blurb: 'Classify track recordings as Normal, Side I or Side II corrugation.',
    path: '/subsystem/rail-corrugation',
  },
  {
    id: 'shm',
    name: 'SHM',
    blurb: 'Estimate cumulative fatigue damage from structural health monitoring data.',
    path: '/subsystem/shm',
  },
]
