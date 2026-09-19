/**
 * The single place the app talks to the backend.
 *
 * Nothing calls this yet - the API does not exist. It is here so that when the
 * first subsystem page needs it, there is one place to add auth headers and
 * error handling rather than four scattered `fetch` calls.
 *
 * The path is always relative, which keeps requests same-origin in dev (Vite
 * proxies /api to the local service) and in production (the host rewrites
 * /api/** to the API service). CORS therefore never enters the picture.
 */

const API_PREFIX = '/api'

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  // TODO: attach an Authorization header here once real auth is wired up.
  return fetch(`${API_PREFIX}${path}`, init)
}
