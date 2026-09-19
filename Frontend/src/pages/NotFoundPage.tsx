import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center bg-slate-50 px-4 text-center">
      <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Page not found</h1>
      <p className="mt-2 text-sm text-slate-600">That page does not exist.</p>
      <Link to="/" className="mt-6 text-sm font-medium text-sky-700 hover:text-sky-800">
        ← Back to start
      </Link>
    </div>
  )
}
