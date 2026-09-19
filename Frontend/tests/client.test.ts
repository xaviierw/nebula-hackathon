import { beforeEach, expect, it, vi } from 'vitest'
const { user, auth, signOut } = vi.hoisted(() => {
  const user = { getIdToken: vi.fn() }
  return { user, auth: { currentUser: user as typeof user | null, authStateReady: vi.fn() }, signOut: vi.fn() }
})
vi.mock('../src/firebase', () => ({ firebaseAuth: auth }))
vi.mock('firebase/auth', () => ({ signOut }))
import { apiFetch } from '../src/api/client'

beforeEach(() => {
  auth.currentUser = user
  user.getIdToken.mockReset().mockResolvedValue('test-only-token')
  signOut.mockReset().mockResolvedValue(undefined)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}')))
})
it('attaches the token and preserves caller headers and body', async () => {
  const body = new FormData()
  await apiFetch('/shm/predict', { method: 'POST', body, headers: { 'X-Test': 'yes' } })
  const [url, request] = vi.mocked(fetch).mock.calls[0]
  expect(url).toBe('/api/shm/predict')
  expect(new Headers(request?.headers).get('Authorization')).toBe('Bearer test-only-token')
  expect(new Headers(request?.headers).get('X-Test')).toBe('yes')
  expect(request?.body).toBe(body)
})
it('refreshes an expired ID token and retries once', async () => {
  vi.mocked(fetch).mockResolvedValueOnce(new Response('{}', { status: 401 })).mockResolvedValueOnce(new Response('{}'))
  expect((await apiFetch('/shm/predict')).status).toBe(200)
  expect(user.getIdToken.mock.calls).toEqual([[false], [true]])
  expect(signOut).not.toHaveBeenCalled()
})
it('signs out after a rejected refresh and never loops', async () => {
  vi.mocked(fetch).mockResolvedValue(new Response('{"message":"Session expired"}', { status: 401 }))
  expect((await apiFetch('/shm/predict')).status).toBe(401)
  expect(fetch).toHaveBeenCalledTimes(2)
  expect(signOut).toHaveBeenCalledOnce()
})
it('requires a signed-in user and handles token refresh failure', async () => {
  auth.currentUser = null
  await expect(apiFetch('/shm/predict')).rejects.toThrow('Sign in')
  expect(fetch).not.toHaveBeenCalled()
  auth.currentUser = user
  vi.mocked(fetch).mockResolvedValueOnce(new Response('{}', { status: 401 }))
  user.getIdToken.mockResolvedValueOnce('old').mockRejectedValueOnce(new Error('revoked'))
  await expect(apiFetch('/shm/predict')).rejects.toThrow('session has expired')
  expect(signOut).toHaveBeenCalledOnce()
})
