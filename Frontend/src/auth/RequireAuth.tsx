import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from './useAuth'

/**
 * Layout route that gates everything nested inside it. Rendering <Outlet /> is
 * what lets the guard wrap a whole branch of the route tree rather than being
 * repeated on every protected page.
 */
export function RequireAuth() {
  const { isAuthed, isLoading } = useAuth()
  if (isLoading) {
    return (
      <div role="status" className="flex min-h-dvh items-center justify-center bg-slate-50 text-sm text-slate-600">
        Checking your session…
      </div>
    )
  }
  return isAuthed ? <Outlet /> : <Navigate to="/login" replace />
}
