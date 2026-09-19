import { createContext } from 'react'
import type { User } from 'firebase/auth'

export interface AuthValue {
  isAuthed: boolean
  isLoading: boolean
  user: User | null
  configurationError: string | null
  authenticationError: string | null
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthValue | null>(null)
