// Compatibility exports for subsystem code written before Firebase setup was
// consolidated at src/firebase.ts. Keeping one initializer prevents duplicate
// app instances and configuration checks from drifting apart.
export {
  firebaseAuth,
  firebaseConfigurationError as authConfigurationError,
} from '../firebase'
