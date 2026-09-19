import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
const { state, api } = vi.hoisted(() => ({ state: { callback: undefined as ((user: unknown) => Promise<void>) | undefined }, api: vi.fn() }))
vi.mock('../src/firebase', () => ({
  firebaseAuth: {},
  firebaseConfigurationError: null,
  requireFirebaseAuth: vi.fn(),
}))
vi.mock('../src/api/client', () => ({ apiFetch: api }))
vi.mock('firebase/auth', () => ({
  onAuthStateChanged: vi.fn((_auth, callback) => { state.callback = callback; return () => {} }),
  signInWithEmailAndPassword: vi.fn(), signOut: vi.fn(),
}))
import { AuthProvider } from '../src/auth/AuthProvider'
import { RequireAuth } from '../src/auth/RequireAuth'
import { useAuth } from '../src/auth/useAuth'
function Login() { return <p>Login: {useAuth().authenticationError}</p> }
function mount() {
  render(<AuthProvider><MemoryRouter initialEntries={['/private']}><Routes>
    <Route element={<RequireAuth />}><Route path="/private" element={<p>Private page</p>} /></Route>
    <Route path="/login" element={<Login />} />
  </Routes></MemoryRouter></AuthProvider>)
}
afterEach(cleanup)
it('waits for restored Firebase state and shared session validation before rendering', async () => {
  let resolve!: (response: Response) => void
  api.mockReturnValue(new Promise(done => { resolve = done }))
  mount()
  expect(screen.getByRole('status').textContent).toContain('Checking')
  expect(screen.queryByText(/Login:/)).toBeNull()
  let completion!: Promise<void>
  act(() => { completion = state.callback!({ uid: 'test' }) })
  expect(screen.getByRole('status')).toBeTruthy()
  await act(async () => { resolve(new Response('{}')); await completion })
  expect(screen.getByText('Private page')).toBeTruthy()
  expect(api).toHaveBeenCalledWith('/auth/session', { method: 'POST' })
})
it('redirects only once restoration confirms no user', async () => {
  mount()
  await act(async () => state.callback!(null))
  expect(screen.getByText(/Login:/)).toBeTruthy()
})
it('shows an unavailable backend error instead of authenticating', async () => {
  api.mockResolvedValue(new Response('{"message":"Sign-in service unavailable"}', { status: 503 }))
  mount()
  await act(async () => state.callback!({ uid: 'test' }))
  await waitFor(() => expect(screen.getByText(/Sign-in service unavailable/)).toBeTruthy())
  expect(screen.queryByText('Private page')).toBeNull()
})
