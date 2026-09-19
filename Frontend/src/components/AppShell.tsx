import { Link, Outlet, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/useAuth'

/**
 * Chrome for the signed-in part of the app. Landing and Login deliberately sit
 * outside it - a "Log Out" button before anyone has logged in makes no sense.
 */
export function AppShell() {
  const { logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/', { replace: true })
  }

  return (
    <div className="min-h-dvh bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-4">
          <Link
            to="/home"
            className="text-lg font-semibold tracking-tight text-slate-900 hover:text-sky-700"
          >
            Nebula
            <span className="ml-2 text-sm font-normal text-slate-500">Rail Diagnostics</span>
          </Link>
          <button
            type="button"
            onClick={handleLogout}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100"
          >
            Log Out
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-10">
        <Outlet />
      </main>
    </div>
  )
}
