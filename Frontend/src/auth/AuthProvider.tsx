import { FirebaseError } from 'firebase/app'
import { onAuthStateChanged, signInWithEmailAndPassword, signOut } from 'firebase/auth'
import type { User } from 'firebase/auth'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'

import { apiFetch } from '../api/client'
import {
  firebaseAuth,
  firebaseConfigurationError,
  requireFirebaseAuth,
} from '../firebase'
import { AuthContext } from './auth-context'
import type { AuthValue } from './auth-context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(firebaseAuth !== null)
  const [authenticationError, setAuthenticationError] = useState<string | null>(null)
  const loginInProgress = useRef(false)

  useEffect(() => {
    if (firebaseAuth === null) return
    let generation = 0
    return onAuthStateChanged(firebaseAuth, async (nextUser) => {
      // signInWithEmailAndPassword updates Firebase state before the backend
      // has accepted /auth/session. Let login() finish that handshake first,
      // otherwise the route guard can briefly admit a rejected account.
      if (loginInProgress.current) return
      const current = ++generation
      setUser(null)
      setAuthenticationError(null)
      setIsLoading(true)
      try {
        if (nextUser) {
          const response = await apiFetch('/auth/session', { method: 'POST' })
          if (!response.ok) {
            throw new Error(await problemMessage(response, 'Sign-in could not be verified.'))
          }
        }
        if (current === generation) setUser(nextUser)
      } catch (error) {
        if (current === generation) {
          setAuthenticationError(error instanceof Error ? error.message : 'Cannot reach the sign-in service.')
        }
      } finally {
        if (current === generation) setIsLoading(false)
      }
    })
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const auth = requireFirebaseAuth()
    loginInProgress.current = true
    setAuthenticationError(null)
    try {
      const credential = await signInWithEmailAndPassword(auth, email, password)
      const response = await apiFetch('/auth/session', { method: 'POST' })
      if (!response.ok) {
        const message = await problemMessage(response, 'The backend could not start your session.')
        throw new Error(message)
      }
      setUser(credential.user)
    } catch (error) {
      if (auth.currentUser) await signOut(auth).catch(() => undefined)
      setUser(null)
      setAuthenticationError(error instanceof Error ? error.message : 'Sign-in failed. Please try again.')
      if (error instanceof FirebaseError) throw new Error(firebaseMessage(error))
      throw error
    } finally {
      loginInProgress.current = false
    }
  }, [])

  const logout = useCallback(async () => {
    const auth = requireFirebaseAuth()
    await signOut(auth)
    setUser(null)
  }, [])

  const value = useMemo<AuthValue>(() => ({
    isAuthed: user !== null,
    isLoading,
    user,
    configurationError: firebaseConfigurationError,
    authenticationError,
    login,
    logout,
  }), [authenticationError, isLoading, login, logout, user])

  return <AuthContext value={value}>{children}</AuthContext>
}

async function problemMessage(response: Response, fallback: string): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (body !== null && typeof body === 'object' && 'message' in body) {
      const message = (body as { message?: unknown }).message
      if (typeof message === 'string') return message
    }
  } catch {
    // A proxy may return HTML; keep the stable fallback.
  }
  return fallback
}

function firebaseMessage(error: FirebaseError): string {
  switch (error.code) {
    case 'auth/invalid-credential':
    case 'auth/invalid-email':
    case 'auth/user-not-found':
    case 'auth/wrong-password':
      return 'The email or password is incorrect.'
    case 'auth/user-disabled':
      return 'This account has been disabled. Contact your administrator.'
    case 'auth/too-many-requests':
      return 'Too many unsuccessful attempts. Wait a moment and try again.'
    case 'auth/network-request-failed':
      return 'Could not reach Firebase Authentication. Check your connection and try again.'
    default:
      return 'Sign-in failed. Please try again.'
  }
}
