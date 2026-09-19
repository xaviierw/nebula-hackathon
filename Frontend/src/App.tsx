import { Route, Routes } from 'react-router-dom'

import { RequireAuth } from './auth/RequireAuth'
import { AppShell } from './components/AppShell'
import { HomePage } from './pages/HomePage'
import { LandingPage } from './pages/LandingPage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { AcvPage } from './pages/subsystems/AcvPage'
import { DoorPage } from './pages/subsystems/DoorPage'
import { RailCorrugationPage } from './pages/subsystems/RailCorrugationPage'
import { ShmPage } from './pages/subsystems/ShmPage'

/**
 * The whole route tree.
 *
 * Landing and Login sit outside AppShell, so the signed-in header (with its Log
 * Out button) never appears before anyone has logged in. RequireAuth and
 * AppShell are layout routes: they wrap a branch of the tree rather than being
 * repeated on each page.
 *
 * Paths are duplicated from subsystems.ts rather than generated, because each
 * route renders a different component - generating them would buy nothing and
 * hide the mapping.
 */
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />

      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route path="/home" element={<HomePage />} />
          <Route path="/subsystem/door" element={<DoorPage />} />
          <Route path="/subsystem/acv" element={<AcvPage />} />
          <Route path="/subsystem/rail-corrugation" element={<RailCorrugationPage />} />
          <Route path="/subsystem/shm" element={<ShmPage />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
