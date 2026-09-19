/**
 * The single place the app talks to the backend.
 *
 * The path is always relative, which keeps requests same-origin in dev (Vite
 * proxies /api to the local service) and in production (the host rewrites
 * /api/** to the API service). CORS therefore never enters the picture.
 */

import { signOut } from 'firebase/auth'

import { firebaseAuth } from '../firebase'

const API_PREFIX = '/api'

export class SessionError extends Error {}

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const auth = firebaseAuth
  if (auth === null) throw new SessionError('Sign-in is not configured. Contact the team.')

  await auth.authStateReady()
  const user = auth.currentUser
  if (!user) throw new SessionError('Sign in to continue.')

  const send = async (forceRefresh: boolean) => {
    let token: string
    try {
      token = await user.getIdToken(forceRefresh)
    } catch {
      throw new SessionError('Your session has expired. Please sign in again.')
    }
    const headers = new Headers(init?.headers)
    headers.set('Authorization', `Bearer ${token}`)
    return fetch(`${API_PREFIX}${path}`, { ...init, headers })
  }

  let response = await send(false)
  if (response.status === 401) {
    // Firebase ID tokens expire after about an hour. Force one refresh and
    // replay the request once; a second 401 is a real authentication failure.
    try {
      response = await send(true)
    } catch (error) {
      await signOut(auth).catch(() => undefined)
      throw error
    }
    if (response.status === 401) await signOut(auth).catch(() => undefined)
  }
  return response
}
