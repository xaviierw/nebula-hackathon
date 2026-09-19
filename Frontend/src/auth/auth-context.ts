import { createContext } from 'react'

export interface AuthValue {
  isAuthed: boolean
  /** Unconditional by design - the scaffold accepts any credentials, including none. */
  login: () => void
  logout: () => void
}

export const AuthContext = createContext<AuthValue | null>(null)

/** Survives a page refresh so a demo does not get bounced back to /login. */
export const AUTH_STORAGE_KEY = 'nebula.isAuthed'
