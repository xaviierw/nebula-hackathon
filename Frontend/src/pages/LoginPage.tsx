import { useState } from 'react'
import { Navigate } from 'react-router-dom'

import { useAuth } from '../auth/useAuth'

export function LoginPage() {
  const { configurationError, isAuthed, isLoading, login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (isLoading) return <LoginStatus message="Checking your session…" />
  if (isAuthed) return <Navigate to="/home" replace />

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (configurationError) return
    setSubmitting(true)
    setError(null)
    try {
      await login(email.trim(), password)
      navigate('/home', { replace: true })
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Sign-in failed. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const disabled = submitting || configurationError !== null
  return (
    <div className="flex min-h-dvh items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm">
        <h1 className="text-center text-2xl font-semibold tracking-tight text-slate-900">
          Sign in
        </h1>

        <form onSubmit={handleSubmit} className="mt-8 space-y-4">
          {configurationError && (
            <p role="alert" className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950">
              {configurationError}
            </p>
          )}
          {error && (
            <p role="alert" className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
              {error}
            </p>
          )}

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-slate-700">
              Email
            </label>
            <input id="email" type="email" required autoComplete="email" value={email}
              disabled={disabled} onChange={(event) => setEmail(event.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 disabled:bg-slate-100" />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-700">
              Password
            </label>
            <input id="password" type="password" required autoComplete="current-password"
              value={password} disabled={disabled} onChange={(event) => setPassword(event.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 disabled:bg-slate-100" />
          </div>

          <button type="submit" disabled={disabled}
            className="w-full rounded-md bg-sky-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-sky-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50">
            {submitting ? 'Signing in…' : 'Log In'}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-slate-500">
          Use the email/password account created by your Firebase administrator.
        </p>
      </div>
    </div>
  )
}

function LoginStatus({ message }: { message: string }) {
  return (
    <div role="status" className="flex min-h-dvh items-center justify-center bg-slate-50 text-sm text-slate-600">
      {message}
    </div>
  )
}
