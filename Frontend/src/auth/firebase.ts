import { initializeApp } from 'firebase/app'
import { getAuth } from 'firebase/auth'

const config = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
}

export const authConfigurationError = Object.values(config).every(Boolean)
  ? '' : 'Sign-in is not configured. Ask the team to configure Firebase for this app.'
export const firebaseAuth = authConfigurationError ? null : getAuth(initializeApp(config))
