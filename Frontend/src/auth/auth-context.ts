import { createContext } from 'react'

export interface AuthValue {
  isAuthed: boolean
  loading: boolean
  error: string
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthValue | null>(null)
