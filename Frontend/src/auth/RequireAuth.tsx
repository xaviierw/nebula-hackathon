import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from './useAuth'

/**
 * Layout route that gates everything nested inside it. Rendering <Outlet /> is
 * what lets the guard wrap a whole branch of the route tree rather than being
 * repeated on every protected page.
 */
export function RequireAuth() {
  const { isAuthed } = useAuth()
  return isAuthed ? <Outlet /> : <Navigate to="/login" replace />
}
