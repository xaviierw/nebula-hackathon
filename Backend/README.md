# Nebula backend

FastAPI service behind the React frontend. One API, four condition-monitoring
subsystems, Firebase Auth for sign-in and Firestore for history.

**Status:** Door, Rail Corrugation and SHM are wired into the shared API. ACV
remains a skeleton returning HTTP 501.

---

## Quick start

```powershell
# from the repo root, once
.venv\Scripts\python.exe -m pip install -r Backend\requirements.txt

# configure
copy Backend\.env.example Backend\.env
#   then edit Backend\.env and point FIREBASE_CREDENTIALS_FILE at your
#   service account JSON -- see "Firebase setup" below

# run
cd Backend
..\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Interactive docs at <http://127.0.0.1:8000/api/docs>.
Health, unauthenticated, at <http://127.0.0.1:8000/api/health>.

The host and port are **not** configurable. `Frontend/vite.config.ts` proxies
`/api` to `127.0.0.1:8000`, which is also why there is no CORS middleware —
every request the browser makes is same-origin.

> In PowerShell, `curl` is an alias for `Invoke-WebRequest` and does not take
> `-F` or `-H` the way you expect. Always type **`curl.exe`**.

---

## How a prediction works

```
browser                    API                          Firestore
   |                        |                               |
   |-- POST /api/{sub}/predict -->                          |
   |   multipart, field "file"                              |
   |                        |-- verify Firebase ID token    |
   |                        |-- sha256(bytes)               |
   |                        |-- look up cache key --------->|
   |                        |<-- hit? return stored result -|
   |                        |                               |
   |                        |-- miss: run the model         |
   |                        |-- store result -------------->|
   |                        |-- record run in history ----->|
   |                        |-- discard the bytes           |
   |<-- {detail, warnings} -|                               |
```

**Uploaded bytes are never persisted.** They are read into memory, hashed,
predicted on, and dropped when the request ends. Nothing writes them to disk,
Firestore or Cloud Storage. Datasets, references and example submissions are
not uploaded to any database.

**The same file is never analysed twice.** Results are cached on
`(subsystem, model_version, sha256)` with no user id in the key, so if any
employee has already run a file, everyone gets the stored result instantly.
Each user still gets their own history entry pointing at it.

---

## The four subsystems

Each has a different task shape and a **different output schema**. They are not
interchangeable — a single generic response model does not fit all four.

| Subsystem | id | Task | Submission CSV | Upload mode |
|---|---|---|---|---|
| **Door** ✅ | `door` | Temporal segment detection | `start_time,end_time,prediction` — **no `file_id`**, one row per segment | `stream` |
| **ACV** ⬜ | `acv` | Fault localisation / ranking | `file_id,ranked_cars` — **no `prediction` column**, car ids `\|`-separated | `per-file` |
| **Rail Corrugation** ✅ | `rail-corrugation` | 3-class classification | `file_id,prediction` ∈ `Normal`/`Side I`/`Side II` | `per-file` |
| **SHM** ✅ | `shm` | Regression | `file_id,prediction` — numeric | `per-file` |

Source: `01_Problem_Statement_3_Specifications.md` §4.1.

Door is the odd one out: the only subsystem with no `file_id`, and the only one
producing many rows from a single input. The other three are one-row-per-file,
which is why every subsystem also exposes `/predict-batch` — building a
submission CSV needs many files in one pass.

Ids match `SubsystemId` in `Frontend/src/subsystems.ts` exactly, hyphen and all.
They are the URL slug on both sides.

### ACV is blocked on data

`02_Datasets/` and `03_References/` contain **only `Door/`**. There is no ACV
dataset or info kit in this repo. Rail's fitted inference bundle and analysis
notebook are committed under `Rail_Corrugation/`; its large source recordings
remain intentionally ignored. SHM's portable inference artifact is committed
under `SHM/artifacts/` and does not require its training data at runtime.

The problem statement calls each info kit *"the authoritative problem
definition"* and says to read it before starting. Whoever owns each subsystem
needs that material before any feature work. Their skeletons are buildable
regardless — structure, CLI, error types and the API seam do not depend on data.
### Dataset availability for SHM
SHM's optional local data lives in。
`SHM/dataset_shm/SHM`, with saved validation outputs in `SHM/outputs/grouped`.
Its deployed `SHM/artifacts/model.json` is tracked and needs no training data
at runtime.

---

## Building a subsystem

Full brief in each directory's own README:
[`ACV/README.md`](ACV/README.md) ·
[`Rail_Corrugation/README.md`](Rail_Corrugation/README.md) ·
[`SHM/README.md`](SHM/README.md)

Door and the unfinished subsystem scaffolds use this layout. SHM keeps its
existing offline training modules at its package root and uses `artifacts/`
and `outputs/`; see [its final layout](SHM/README.md#shared-inference-package).

```
<Subsystem>/
  main.py                  CLI: train / predict / evaluate
  requirements.txt         split INFERENCE vs TRAINING
  README.md                the brief
  core/data.py             column constants, read_raw(), check_schema()
  core/features.py         feature extraction
  core/model.py            load + predict
  core/errors.py           <X>InputError / <X>ModelError
  training/train.py        writes ./model artifacts
  training/evaluate.py     scores against the info kit's fixed metric
  prediction/predict.py    <- the one file the API calls
  model/  output/          generated, gitignored
```

### The only signature that is not yours to choose

```python
# prediction/predict.py

def predict_file(frame: pd.DataFrame, model, reference: dict | None = None) -> dict:
    """Pure. No file IO, no printing, no sys.exit. Returns JSON-ready data."""
```

Three rules, all learned on Door:

1. **Raise, never `sys.exit`.** `SystemExit` inherits from `BaseException`, so a
   caller's `except Exception` misses it and the server dies instead of showing
   the message. `Door/core/errors.py` explains this in its own docstring.
2. **`<X>InputError` messages are shown to users verbatim.** Write them for a
   non-technical reader. Multi-line is fine — the frontend renders with
   `whitespace-pre-line`.
3. **Return plain `int`/`float`/`str`.** `np.int64` is not a subclass of `int`
   and Pydantic rejects it.

Keep it deterministic: the cache will not re-run your model on a file it has
already seen.

### Wiring it in

Two files, no routes:

1. Fill in `app/subsystems/<mod>/runner.py` — copy
   [`app/subsystems/door/runner.py`](app/subsystems/door/runner.py), the worked
   reference.
2. In [`app/subsystems/registry.py`](app/subsystems/registry.py), swap one line:

```python
- register(NotImplementedRunner("acv", "ACV"))
+ register(AcvRunner())
```

Auth, caching, history and error mapping come for free. Confirm with
`curl.exe http://127.0.0.1:8000/api/health` — your subsystem should report
`"available": true` with a real `model_version`.

> **Import-name collision, read before wiring the second subsystem.** Door
> occupies the top-level module names `core`, `training` and `prediction` via
> its `vendor_path.py` shim. The next subsystem to be wired in **cannot** reuse
> those names — give it a package root, or rename to `acv_core` /
> `acv_prediction`. SHM uses qualified `SHM.*` imports and coexists with Door.

---

## API

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/health` | no | Status + per-subsystem availability |
| GET | `/api/subsystems` | no | id, name, available, model_version, upload_mode |
| POST | `/api/auth/session` | yes | Call once after sign-in; creates the user doc |
| GET | `/api/auth/me` | yes | Verify a token, read-only |
| POST | `/api/auth/revoke` | yes | Invalidate this user's refresh tokens |
| GET | `/api/users/me` | yes | Profile |
| PATCH | `/api/users/me` | yes | Set display name |
| GET | `/api/users/me/runs` | yes | History, newest first, cursor-paginated |
| GET | `/api/users/me/runs/{run_id}` | yes | Re-view a past prediction |
| POST | `/api/{subsystem}/predict` | yes | One file |
| POST | `/api/{subsystem}/predict-batch` | yes | Many files |

There is no `/logout` on purpose: Firebase sign-out happens entirely in the
browser, and an endpoint that returns 204 and does nothing would be misleading.
`/auth/revoke` is the real server-side sign-out.

### The error envelope

**Every** error is `{"message": "..."}` — never FastAPI's default
`{"detail": ...}`.

That is not style. The Door success body already has a top-level `detail` field
(the per-cycle rows), and `Frontend/src/features/door/runPrediction.ts` reads
`problem.message`. A `detail` key on an error would collide with the success
shape.

[`app/errors.py`](app/errors.py) installs five handlers to guarantee it,
including one bound to **Starlette's** `HTTPException` rather than FastAPI's —
binding only to FastAPI's would leave router-generated 404s and 405s returning
the default envelope.

| Status | When |
|---|---|
| 400 | Bad input — wrong columns, empty file, unparseable timestamps |
| 401 | Missing, expired, revoked or invalid token |
| 403 | Email outside `ALLOWED_EMAIL_DOMAINS` |
| 404 | Unknown subsystem or run |
| 410 | Past result gone — the model was retrained since |
| 413 | Upload over `MAX_UPLOAD_BYTES` |
| 422 | Malformed request (e.g. no `file` part) |
| 501 | Subsystem not built yet |
| 503 | Model built but not installed here, or Firestore unreachable |

### Door response — frozen

Mirrors `Frontend/src/features/door/types.ts` exactly, which mirrors
`DoorClassifier.DETAIL_COLUMNS`. Change one, change all three.

```json
{
  "detail": [{
    "start_time": "2023-7-5-0-0-0-0",
    "end_time": "2023-7-5-0-0-3-760",
    "start_row": 0,
    "end_row": 188,
    "operation": "Close",
    "steady_current_mA": 195.1,
    "threshold_mA": 251.5,
    "prediction": "Normal",
    "margin_ratio": -0.484
  }],
  "warnings": []
}
```

Two things that look like tidy-up opportunities and are not:

- **Timestamps are the dataset's native `Y-M-D-H-M-S-ms`, not ISO-8601.**
  Zero-padding stripped. Produced by `core/scoring.py format_time`; the frontend
  has its own `formatTime.ts` to read it. If you see `2023-07-05T00:00:00`,
  something bypassed `format_time`.
- **Never add a Pydantic `alias_generator`.** These field names *are* the wire
  format. `steady_current_mA` under `to_camel` becomes `steadyCurrentMA` and the
  results table renders empty cells.

Cache status comes back as headers — `X-Prediction-Cache: hit|miss` and
`X-Run-Id` — because the success body is frozen and cannot grow fields.

---

## Firestore

Four collections. No uploaded bytes anywhere.

**`users/{uid}`** — document id *is* the Firebase uid, so there is no lookup
table. `{uid, email, display_name, photo_url, created_at, last_seen_at, sign_in_count}`

**`predictions/{subsystem}__{model_version}__{sha256}`** — the shared cache.
No uid in the key, so any employee uploading the same file hits the same
document. `model_version` is in the key, so **retraining invalidates everything
automatically** — no purge script, and old results stay readable for history.

`payload_json` is stored as a JSON **string**, not a nested map: exact
round-trip, no index bloat from thousands of rows, and it sidesteps Firestore's
"arrays cannot contain arrays" rule that `warnings[].observed` sails close to.

**`users/{uid}/runs/{run_id}`** — history, as a **subcollection**. Listing one
user's runs needs no composite index and no `where("uid", "==")` anyone could
forget, so cross-user leakage is structurally impossible rather than a
code-review item. Failed uploads are recorded too (`status: "error"`).

**`datasets/{sha256}`** — metadata only: size, how many times seen, which
filenames, which subsystems. Never contents.

**Security rules: deny-all.** The frontend never touches Firestore directly —
only the Admin SDK does, and it bypasses rules entirely.

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} { allow read, write: if false; }
  }
}
```

---

## Auth

Firebase JS SDK signs in → `getIdToken()` → `Authorization: Bearer <token>` →
`verify_id_token()` → `CurrentUser`.

**One kind of user.** Every authenticated employee has identical permissions.
There is no role, tier or permission field anywhere, by design.

**But "one kind of user" is not the same as "anyone may sign up."** Firebase
Auth with a public provider enabled will authenticate any account in the world.
This is an internal tool, so gate membership two ways:

1. Enable **Email/Password only** and create accounts by hand in the Firebase
   console. There is no sign-up UI in `LoginPage.tsx` anyway, so this is free.
2. Set `ALLOWED_EMAIL_DOMAINS=yourcompany.com`.

Neither is RBAC. Both are membership.

The dependency distinguishes **expired** from **invalid** tokens so the frontend
can silently call `getIdToken(true)` and retry once, instead of bouncing people
to `/login` every hour.

---

## Configuration

### `Backend/.env` — gitignored

| Variable | Secret? | Notes |
|---|---|---|
| `FIREBASE_CREDENTIALS_FILE` | **the file it points at is** | Store the JSON **outside the repo** |
| `FIREBASE_PROJECT_ID` | no | Same value as the frontend's |
| `ALLOWED_EMAIL_DOMAINS` | no | Empty = anyone Firebase accepts |
| `MAX_UPLOAD_BYTES` | no | Default 25 MiB |
| `PREDICTION_CACHE_ENABLED` | no | `false` to benchmark cold runs |
| `LOG_LEVEL` | no | |

Credentials are loaded with an explicit `credentials.Certificate(path)`, not
Application Default Credentials. With the gcloud SDK installed — as it is on
this machine — ADC silently picks up a developer's personal gcloud login and
appears to work, against whatever project that login defaults to.

### `Frontend/.env.local` — all public

`VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`,
`VITE_FIREBASE_APP_ID`

**`VITE_FIREBASE_API_KEY` is not a secret**, despite the name. It is a project
identifier, baked into the JS bundle by design, and Google intends it to be
public. Security comes from auth providers, authorized domains and Firestore
rules — not from hiding it.

Use `.env.local` specifically: the root `.gitignore` covers
`Frontend/.env*.local`.

Copy `Frontend/.env.example` to `Frontend/.env.local` and fill the public values.
The frontend now implements Firebase Email/Password sign-in, session restoration,
shared `/auth/session` verification, and one token-refresh retry on 401.

### Firebase setup, one-time

1. Create a project, skip Analytics.
2. Authentication → enable **Email/Password**. Add team accounts by hand.
3. Firestore → Create database → **Production mode** → `asia-southeast1`.
4. Paste the deny-all rules above.
5. **Firestore → Indexes → Single field → add an exemption for `payload_json`
   in `predictions`**, disabling ascending/descending/array-contains. Indexed
   strings hit a 1500-byte index-entry ceiling and large cache writes are
   rejected without this.
6. Project settings → Service accounts → Generate new private key → save
   outside the repo.
7. Project settings → General → Web app → copy config into
   `Frontend/.env.local`.

---

## Startup behaviour

| Condition | Behaviour |
|---|---|
| Firebase credentials missing or bad | **Crash.** Every route needs auth; a server that cannot verify tokens is not partially useful |
| Firestore unreachable | Not probed at startup; per-request 503 |
| `SHM/artifacts/model.json` missing/incompatible | **Degrade.** Only SHM returns 503; reason appears in `/api/health` |
| `door_model.json` missing | **Degrade.** Door → 503 with an actionable message; auth, history and the other subsystems still work |
| `door_reference.json` missing | Degrade silently, log once. `warnings` is `[]` — known and correct |
| `core` resolves outside `Backend/Door` | **Crash.** A wrong import would produce confidently wrong predictions |

One subsystem failing to load never takes down the others.

---

## Verification

Door is verified working end to end:

```
model_version  door-1:d36ac68f076f
input          02_Datasets/Door/Test.csv, 401434 bytes
output         38 detail rows, 8 abnormal, 0 warnings
elapsed        65 ms
first row      2023-7-5-0-0-0-0 .. 2023-7-5-0-0-3-760, Close, Normal
```

Reproduce without starting the server or touching Firebase:

```powershell
cd Backend
..\.venv\Scripts\python.exe -c "import sys,os; sys.path.insert(0,os.path.abspath('.')); from app.subsystems.door.runner import DoorRunner; r=DoorRunner(); r.load(); o=r.run(open('02_Datasets/Door/Test.csv','rb').read(),'Test.csv'); print(len(o['detail']),'rows', o['detail'][0]['start_time'])"
```

Expect `38 rows 2023-7-5-0-0-0-0`.

### Against a running server

Get a token without the frontend, via the Identity Toolkit REST API:

```powershell
$key  = "<VITE_FIREBASE_API_KEY>"
$body = '{"email":"you@company.com","password":"...","returnSecureToken":true}'
$T = (Invoke-RestMethod -Method Post -ContentType application/json -Body $body `
  -Uri "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=$key").idToken
```

```powershell
# 401, body exactly {"message":"Sign in to continue."}
curl.exe -i -X POST http://127.0.0.1:8000/api/door/predict

# create the user document
curl.exe -X POST -H "Authorization: Bearer $T" http://127.0.0.1:8000/api/auth/session

# the real thing
curl.exe -i -H "Authorization: Bearer $T" -F "file=@02_Datasets/Door/Test.csv" `
  http://127.0.0.1:8000/api/door/predict
```

Assert: 38 `detail` entries; `X-Prediction-Cache: miss` then **`hit`** on an
identical second call — and re-run with a *different user's* token to prove the
cache is shared.

```powershell
# 501 from an unbuilt subsystem
curl.exe -i -H "Authorization: Bearer $T" -F "file=@02_Datasets/Door/Test.csv" `
  http://127.0.0.1:8000/api/acv/predict

# 400 with a readable multi-line message
curl.exe -i -H "Authorization: Bearer $T" `
  -F "file=@04_Example_Submission/door_predictions.csv" `
  http://127.0.0.1:8000/api/door/predict

# 422 -- must contain "message", must NOT contain a top-level "detail"
curl.exe -i -H "Authorization: Bearer $T" -X POST http://127.0.0.1:8000/api/door/predict

# history
curl.exe -H "Authorization: Bearer $T" http://127.0.0.1:8000/api/users/me/runs
```

---

## Connecting the frontend

Firebase authentication is connected in the frontend: email/password login,
session restoration, bearer tokens and one forced-refresh retry on `401`.
Configure the four `VITE_FIREBASE_*` values in `Frontend/.env.local` using
`Frontend/.env.example`.

Door still serves its fixture. To connect it, update
`src/features/door/runPrediction.ts` using the implementation in its docstring
and set `IS_PLACEHOLDER_DATA = false`.

The results table, summary and CSV download should be identical to the
fixture-driven version but with real numbers, and the demo banner disappears.

---

## Known issues

**`door_reference.json` does not exist**, so `warnings` is always `[]`. The
guards that produce warnings short-circuit without it. Harmless and correct
today — but when a retrain produces one, make sure the warning schema still
passes extra keys through (`extra="allow"` in `app/schemas/common.py`). Pydantic's
default would silently strip `n_segments`, `expected_min`, `observed` and the
rest, and it would look like a model regression rather than a schema bug.

**`Door/output/door_detail.csv` is stale** — it predates `start_row`/`end_row`.
The API never reads it. Don't "fix" it.

**A cache hit is observable by timing**, so a user can in principle learn that a
file was analysed before. Fine for an internal tool.

**`predictions/{key}.first_run_by` must never be returned to a client.** It is
the one cross-user identity leak in this design, stored for debugging only.

---

## Why some non-obvious things are the way they are

**`Backend/Door/` is untouched.** Its modules import each other absolutely
(`from core.data import ...`) and rely on `Backend/Door` being on `sys.path`.
`app/subsystems/door/vendor_path.py` **appends** it — appending, not
`insert(0)`, because at position 0 `Door/main.py` would shadow `Backend/main.py`
and Door's `model/`, `output/` and `training/` folders would become importable
top-level packages. `DoorRunner.load()` then asserts that `core` really did
resolve inside `Backend/Door`, because a silently wrong import would produce
confidently wrong predictions.

**The runner re-implements `load_inputs` instead of calling it.**
`Door/prediction/predict.py:200` takes a `Path` and calls `.exists()`, so it
cannot serve an upload. The runner does the same steps on an `io.BytesIO`,
preserving every error type and message verbatim.

**`MultiPartParser.spool_max_size` is raised in `create_app()`.** Starlette backs
`UploadFile` with a `SpooledTemporaryFile` capped at 1 MiB and silently writes
larger uploads to `%TEMP%` — which would break the "bytes never touch disk"
guarantee. `Test.csv` is 401 KB, so this would not have shown up in testing.

**The API tier never imports `training/`.** Door inference is sklearn-free.
Rail inference loads its committed Extra Trees bundle and therefore pins the
exact NumPy, pandas, SciPy, scikit-learn and joblib versions recorded by that
bundle in `Backend/requirements.txt`. The other subsystems must either produce
artifacts compatible with this shared inference environment or use a
version-neutral format; one Python process cannot safely load incompatible
scikit-learn pickle versions.

**Rail is a real package.** `Rail_Corrugation.predictor` avoids colliding with
Door's top-level `core`, `training` and `prediction` imports. Its API adapter is
bytes-in and uses no temporary upload files.

**Routers are generated from the registry**, not hand-written per subsystem.
That is what makes adding a model a one-line change.

## SHM response and cache

`POST /api/shm/predict` returns prediction, observations, weighted_cycle_count,
model_id (artifact SHA256), model_version (pipeline revision + hash), null
interval, and structured warnings. It never returns a request filename in the
content-cached payload. The frontend associates its selected filename locally;
batch responses and request history retain the current upload's filename.
Sequential single uploads are supported; `/predict-batch` is optional.
SHM uses rainflow 3.2.0 and SciPy logsumexp, with no scikit-learn inference import.
Shared runner InputError/ModelError exceptions are translated to 400/503 before
leaving the router, so both single and batch responses have actionable messages.
