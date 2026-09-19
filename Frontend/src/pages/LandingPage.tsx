import { Link } from 'react-router-dom'

export function LandingPage() {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center bg-slate-50 px-4 text-center">
      <h1 className="text-4xl font-semibold tracking-tight text-slate-900 sm:text-5xl">Nebula</h1>
      <p className="mt-4 max-w-md text-base text-slate-600">
        Predictive diagnostics for rail subsystems.
      </p>
      <Link
        to="/login"
        className="mt-10 rounded-md bg-sky-700 px-6 py-3 text-sm font-semibold text-white hover:bg-sky-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2"
      >
        Log In
      </Link>
    </div>
  )
}
