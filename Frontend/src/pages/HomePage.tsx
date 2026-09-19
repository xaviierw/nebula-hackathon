import { SubsystemCard } from '../components/SubsystemCard'
import { SUBSYSTEMS } from '../subsystems'

export function HomePage() {
  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Subsystems</h1>
      <p className="mt-2 text-sm text-slate-600">
        Choose a subsystem to upload data and run a prediction.
      </p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        {SUBSYSTEMS.map((subsystem) => (
          <SubsystemCard key={subsystem.id} subsystem={subsystem} />
        ))}
      </div>
    </>
  )
}
