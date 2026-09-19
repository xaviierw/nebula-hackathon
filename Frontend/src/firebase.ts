import { initializeApp } from 'firebase/app'
import type { FirebaseOptions } from 'firebase/app'
import { getAuth } from 'firebase/auth'
import type { Auth } from 'firebase/auth'

const firebaseConfig: FirebaseOptions = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
}

const missing = Object.entries(firebaseConfig)
  .filter(([, value]) => (
    typeof value !== 'string' || value.trim() === '' || value.startsWith('your-')
  ))
  .map(([key]) => key)

export const firebaseConfigurationError = missing.length > 0
  ? `Firebase frontend configuration is missing: ${missing.join(', ')}. Copy Frontend/.env.example to Frontend/.env.local and use the Web app values from Firebase.`
  : null

export const firebaseAuth: Auth | null = firebaseConfigurationError
  ? null
  : getAuth(initializeApp(firebaseConfig))

export function requireFirebaseAuth(): Auth {
  if (firebaseAuth === null) {
    throw new Error(firebaseConfigurationError ?? 'Firebase authentication is unavailable.')
  }
  return firebaseAuth
}
