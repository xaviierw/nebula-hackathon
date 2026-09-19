import { useCallback, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { AUTH_STORAGE_KEY, AuthContext } from './auth-context'
import type { AuthValue } from './auth-context'

/**
 * Placeholder authentication.
 *
 * `login()` ignores whatever was typed and always succeeds - the scaffold is
 * meant to be walked through without credentials. What it does provide is the
 * seam: a single function body to replace when real auth arrives, and a guard
 * (RequireAuth) that already wraps the protected routes, so /home cannot be
 * reached just by typing the URL.
 *
 * sessionStorage access is wrapped because it throws in some privacy modes.
 */

function readStoredAuth(): boolean {
  try {
    return sessionStorage.getItem(AUTH_STORAGE_KEY) === 'true'
  } catch {
    return false
  }
}

function writeStoredAuth(isAuthed: boolean): void {
  try {
    if (isAuthed) {
      sessionStorage.setItem(AUTH_STORAGE_KEY, 'true')
    } else {
      sessionStorage.removeItem(AUTH_STORAGE_KEY)
    }
  } catch {
    // Non-fatal: auth then simply does not survive a refresh.
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthed, setIsAuthed] = useState(readStoredAuth)

  const login = useCallback(() => {
    writeStoredAuth(true)
    setIsAuthed(true)
  }, [])

  const logout = useCallback(() => {
    writeStoredAuth(false)
    setIsAuthed(false)
  }, [])

  const value = useMemo<AuthValue>(
    () => ({ isAuthed, login, logout }),
    [isAuthed, login, logout],
  )

  return <AuthContext value={value}>{children}</AuthContext>
}
