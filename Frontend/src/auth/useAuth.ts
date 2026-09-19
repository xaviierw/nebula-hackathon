import { useContext } from 'react'

import { AuthContext } from './auth-context'
import type { AuthValue } from './auth-context'

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (value === null) {
    throw new Error('useAuth must be used inside an <AuthProvider>')
  }
  return value
}
