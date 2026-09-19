/**
 * The single place the app talks to the backend.
 *
 * The path is always relative, which keeps requests same-origin in dev (Vite
 * proxies /api to the local service) and in production (the host rewrites
 * /api/** to the API service). CORS therefore never enters the picture.
 */

import { getIdToken } from 'firebase/auth'

import { firebaseAuth } from '../firebase'

const API_PREFIX = '/api'

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  let response = await send(path, init, false)
  if (response.status === 401 && firebaseAuth?.currentUser) {
    // Firebase ID tokens expire after about an hour. Force one refresh and
    // replay the request once; a second 401 is a real authentication failure.
    response = await send(path, init, true)
  }
  return response
}

async function send(path: string, init: RequestInit | undefined, forceRefresh: boolean) {
  const headers = new Headers(init?.headers)
  const user = firebaseAuth?.currentUser
  if (user) {
    headers.set('Authorization', `Bearer ${await getIdToken(user, forceRefresh)}`)
  }
  return fetch(`${API_PREFIX}${path}`, { ...init, headers })
}
