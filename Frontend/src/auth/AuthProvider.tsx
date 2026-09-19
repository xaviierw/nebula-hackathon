import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { onAuthStateChanged, signInWithEmailAndPassword, signOut } from 'firebase/auth'

import { apiFetch } from '../api/client'
import { AuthContext } from './auth-context'
import type { AuthValue } from './auth-context'
import { authConfigurationError, firebaseAuth } from './firebase'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthed, setIsAuthed] = useState(false)
  const [loading, setLoading] = useState(Boolean(firebaseAuth))
  const [error, setError] = useState(authConfigurationError)
  const retrySession = useRef<(() => Promise<void>) | null>(null)

  useEffect(() => {
    const auth = firebaseAuth
    if (!auth) return
    let generation = 0
    const restoreSession = async (user: typeof auth.currentUser) => {
      const current = ++generation
      setLoading(true)
      setIsAuthed(false)
      setError('')
      try {
        if (user) {
          const response = await apiFetch('/auth/session', { method: 'POST' })
          if (!response.ok) {
            const problem = await response.json().catch(() => null)
            throw new Error(problem?.message ?? 'Sign-in could not be verified. Please retry.')
          }
          if (current === generation) setIsAuthed(true)
        }
      } catch (caught) {
        if (current === generation) setError(caught instanceof Error ? caught.message : 'Cannot reach the sign-in service.')
      } finally {
        if (current === generation) setLoading(false)
      }
    }
    retrySession.current = () => restoreSession(auth.currentUser)
    const unsubscribe = onAuthStateChanged(auth, restoreSession, () => {
      setError('Your session could not be restored. Please sign in again.')
      setLoading(false)
    })
    return () => { generation++; retrySession.current = null; unsubscribe() }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    if (!firebaseAuth) throw new Error(authConfigurationError)
    setError('')
    const previousUser = firebaseAuth.currentUser
    try {
      const credential = await signInWithEmailAndPassword(firebaseAuth, email, password)
      // Firebase need not emit a state change when the same user retries after
      // an unavailable backend. Recheck the shared session explicitly then.
      if (previousUser?.uid === credential.user.uid) await retrySession.current?.()
    }
    catch { throw new Error('Could not sign in. Check your email and password, then retry.') }
  }, [])
  const logout = useCallback(async () => {
    if (firebaseAuth) await signOut(firebaseAuth)
  }, [])

  const value = useMemo<AuthValue>(
    () => ({ isAuthed, loading, error, login, logout }),
    [isAuthed, loading, error, login, logout],
  )
  return <AuthContext value={value}>{children}</AuthContext>
}
