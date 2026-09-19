# SHM app: shared API, prediction and export

## Start locally

Use Python 3.11+ and Node 22.12+. Install from the repository root:

```powershell
.venv/Scripts/python.exe -m pip install -r Backend/requirements.txt
Copy-Item Backend/.env.example Backend/.env
Copy-Item Frontend/.env.example Frontend/.env.local
```

Edit the local configuration before starting. `Backend/.env` needs
`FIREBASE_PROJECT_ID` and `FIREBASE_CREDENTIALS_FILE`, pointing to an existing
service-account JSON **outside the repository**. Configure Firestore and the
allowed email domains as described in [the shared backend guide](../README.md).
Never put private credentials in frontend variables or commit local environment files.

`Frontend/.env.local` needs the web app's public `VITE_FIREBASE_API_KEY`,
`VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, and `VITE_FIREBASE_APP_ID`.
Use the same Firebase project on both sides, enable Email/Password sign-in,
create team accounts, and authorize the development/production hostnames.
Missing web configuration displays an actionable sign-in error.

Start the **only production API**, from `Backend`:

```powershell
cd Backend
../.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

In another terminal, from the repository root:

```powershell
cd Frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open the Vite URL, sign in, choose SHM, select or drop recordings, estimate
fatigue damage, and download `shm_predictions.csv`. The page processes up to
32 files sequentially with per-file progress/errors. Each CSV must have no
header, exactly one numeric column and exactly 581,120 finite observations.
The UI accepts files up to 16 MiB; the shared server defaults to a 25 MiB
request limit. Flat/degenerate recordings cannot produce a supported positive
fatigue moment and are rejected. No observations are transformed or discarded.

**Obsolete:** the old `uvicorn api:app --app-dir Backend/SHM` command and demo
login instructions. `SHM/api.py` has been removed. There is no standalone SHM
health route; use `/api/health` to inspect SHM availability.

## Integration and model

```text
SHM page -> shared apiFetch (Firebase ID token) -> /api/shm/predict
 -> shared auth/cache/router -> ShmRunner -> SHM.core.data
 -> SHM.prediction.predict.predict_file -> SHM.core.features + SHM.core.model
 -> prediction/metadata -> browser associates current filename -> CSV
```

The auth provider waits for Firebase session restoration and shared
`/api/auth/session` verification before rendering protected pages. The shared
client gets the current user's ID token, refreshes and retries once on HTTP
401, and signs out on a second rejection. Backend errors use `{"message":"..."}`.
SDK behavior follows [Firebase's Auth API](https://firebase.google.com/docs/reference/js/auth).

The runner loads **`Backend/SHM/artifacts/model.json`** once at startup. It is
the sole deployed artifact, SHA256
`4f5f84828fcb230b004a6721d82d9f9cc268298596404beab868a0f8f1da0a16`.
Its current selected law is approximately
`D = exp(-20.4156106700493) * sum(count * (range / 2)^5)`.
Parameters are read from the artifact. Rainflow 3.2.0 preserves full cycles
and endpoint half cycles; SciPy logsumexp preserves stable moment accumulation.
Runtime requirements contain no scikit-learn. No labels or training modules
are read/imported in shared inference. The runner parses bytes in memory;
it does not write files, invoke a CLI, or access Firestore.

Responses contain positive finite `prediction`, `observations`,
`weighted_cycle_count`, artifact SHA256 `model_id`, `model_version`,
`interval: null`, and structured `warnings` (currently empty). There is no
validated uncertainty interval or confidence estimate. The existing internal
validation estimate is about **2.59% MAPE**, score **0.9741**; migration does not
improve that estimate or establish hidden-test performance.

`model_version` combines an explicit pipeline revision with the full artifact
fingerprint. Bump the revision when parsing, mechanics or response semantics
change. Shared cache keys use subsystem, model version and content SHA256.
Cached payloads contain no filename; request history and batch envelopes keep
the current filename. The browser supplies the selected file's exact name for
export, including after a cache hit under a new name. All selected files must
succeed under one model/pipeline version before download is enabled. Replacing
a selection clears results. CSV columns are exactly `file_id,prediction`, with
one unique row per recording and unrounded predictions.

`ShmInputError` maps to HTTP 400 and `ShmModelError` to 503 through the shared
router; batch routes report the same messages per file. Missing/incompatible
artifacts mark only SHM unavailable. Door's prediction contract is unchanged.

## Command-line prediction and offline validation

From the repository root:

```powershell
.venv/Scripts/python.exe Backend/SHM/predict.py --input Backend/SHM/dataset_shm/SHM/Test --output Backend/SHM/shm_predictions.csv
```

This directly calls the same core reader, model loader and pure prediction
function as the shared API, without an intermediate inference wrapper.
`--model PATH` explicitly selects another supported physics artifact. The
loader deliberately rejects unsupported model families; experimental training
models are not automatically production models.

The existing offline `main.py audit`, `develop`, `final`, and `all` commands
remain available with `Backend/SHM/requirements.txt`. Their model-selection
procedure is unchanged and their outputs remain under ignored `outputs/`.
They do not overwrite the deployed artifact. See [README.md](README.md).

## Verification

```powershell
.venv/Scripts/python.exe -m pip install -r Backend/requirements.txt -r Backend/SHM/requirements.txt
.venv/Scripts/python.exe -m pytest Backend/SHM/tests/test_pipeline.py Backend/SHM/tests/test_api.py -q
cd Frontend
npm test
npm run build
npm run lint
```

API tests explicitly mock Firebase/Firestore and exercise real shared routes,
including missing auth, invalid tokens, model failure, cache versioning and
batch errors. Real-data parity tests compare all 16 local recordings against
untouched saved predictions by exact filename at rtol=1e-12. They skip when
those ignored local inputs/references are absent. Training tests use synthetic
data to check the unchanged mechanics, splitting and selection rules.
Frontend tests simulate Firebase and fetch to cover loading, refresh, upload,
CSV precision, errors and stale-download protection.

With Vite running and Python Playwright installed, a real browser can exercise
the UI and shared API with explicitly simulated auth/Firestore:

```powershell
.venv/Scripts/python.exe Backend/SHM/tests/browser_smoke.py --simulated-auth
```

The test intercepts auth modules **only inside Playwright** and forwards API
requests to a temporary local instance of the shared FastAPI app. Production has no auth bypass.
Without `--simulated-auth`, it uses the running shared API and real Firebase;
set `SHM_TEST_EMAIL` and `SHM_TEST_PASSWORD` locally for a test account.
Screenshots/downloads go into ignored `outputs/app_smoke/`. Simulated browser
checks are not live Firebase/Firestore validation.

## Files to commit

Commit the SHM package/core/prediction/CLI and compatibility-import changes,
shared runner/registry/schema/router changes, frontend auth/client/SHM changes,
new tests/configuration, dependency manifests and lockfile, environment examples,
and updated documentation. Keep the already-tracked artifact unchanged.
Do not include `refine.py`, `tests/test_refine.py`, `REFINEMENT_RESULTS.md`, raw
datasets, caches, experiment reports, generated CSVs, build output, credentials,
or local environment files. Review explicit paths instead of `git add .`.

## Migration verification result

The migration checks passed: 45 Python tests; 12 frontend tests; TypeScript and
production build; lint; and headless Edge upload/download, refresh, invalid-input,
stale-selection and drag/drop checks. All 16 real test recordings matched the
unchanged saved outputs at rtol=1e-12; the command-line export matched exactly
when parsed as float64. The artifact SHA256 above stayed unchanged.
Firebase and Firestore were simulated in tests, including the browser run.
Live authenticated validation remains pending project configuration and a test
account. No retraining or model refinement was performed.
