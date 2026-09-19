/**
 * The single place the app talks to the backend.
 *
 * SHM uses this client for live predictions. Subsystems share this seam for
 * future auth headers and service configuration.
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
