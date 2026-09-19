/** Shared same-origin client with Firebase token refresh and one 401 retry. */
import { signOut } from 'firebase/auth'
import { firebaseAuth } from '../auth/firebase'

export class SessionError extends Error {}

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const auth = firebaseAuth
  if (!auth) throw new SessionError('Sign-in is not configured. Contact the team.')
  await auth.authStateReady()
  const user = auth.currentUser
  if (!user) throw new SessionError('Sign in to continue.')
  const send = async (refresh: boolean) => {
    let token: string
    try { token = await user.getIdToken(refresh) }
    catch { throw new SessionError('Your session has expired. Please sign in again.') }
    const headers = new Headers(init?.headers)
    headers.set('Authorization', `Bearer ${token}`)
    return fetch(`/api${path}`, { ...init, headers })
  }
  let response = await send(false)
  if (response.status === 401) {
    try { response = await send(true) }
    catch (error) {
      await signOut(auth)
      throw error
    }
    if (response.status === 401) await signOut(auth)
  }
  return response
}
