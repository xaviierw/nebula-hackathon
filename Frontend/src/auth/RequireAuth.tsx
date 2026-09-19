import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from './useAuth'

/**
 * Layout route that gates everything nested inside it. Rendering <Outlet /> is
 * what lets the guard wrap a whole branch of the route tree rather than being
 * repeated on every protected page.
 */
export function RequireAuth() {
  const { isAuthed, loading } = useAuth()
  if (loading) return <p role="status" className="p-8">Restoring your session...</p>
  return isAuthed ? <Outlet /> : <Navigate to="/login" replace />
}
