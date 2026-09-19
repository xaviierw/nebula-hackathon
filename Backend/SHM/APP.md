# SHM app: run, predict and submit

The existing React app now has a live SHM page. It uploads recordings to Python;
the browser does not execute the JSON model. No training data or labels are
needed by the running service.

## Start locally

Use Python 3.12 and the Node version required by the frontend (Node 22.12+).
From the repository root, create a virtual environment if one does not exist:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r Backend/SHM/requirements-api.txt
.venv/Scripts/python.exe -m uvicorn api:app --app-dir Backend/SHM --host 127.0.0.1 --port 8000
```

Keep that terminal open. In a second terminal:

```powershell
cd Frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open the URL Vite prints, normally http://127.0.0.1:5173. Use the existing demo
login (empty credentials work), select **SHM**, choose or drop the recordings,
click **Estimate fatigue damage**, and download **shm_predictions.csv**.

The page supports up to 32 files, including all 16 test recordings, processed
sequentially with progress and per-file errors. Each file must be a nonempty CSV
at most 16 MiB, with exactly 581,120 finite numeric rows, one column, no header.
Constant/degenerate signals are rejected because the validated extractor requires
positive fatigue moments. Failed batches cannot produce a partial submission;
correct inputs and rerun. Selecting new files clears the previous results.

The frontend uses relative `/api/shm/predict` requests. Vite proxies `/api` to
port 8000. For deployment, build with `npm run build`, serve `Frontend/dist` with
SPA fallback, and configure the host to proxy `/api` to the Python service.
Configure upload limits for at least 16 MiB plus multipart overhead and timeouts
long enough for a complete recording. This is a local integration, not a hosted
deployment. The existing login is a demo UI, not API authentication.

## What runs at prediction time

```text
ShmPage.tsx → features/shm/prediction.ts → POST /api/shm/predict
  → api.py → inference.py → data.py (parse + rainflow)
  → models.py (saved calibrated fatigue law) + artifacts/model.json
  → {file_id, prediction, observations, weighted_cycle_count, model_id}
  → browser table → shm_predictions.csv
```

`api.py` loads the model once at startup. CPU work runs outside the async event
loop, with two counting operations allowed concurrently. Uploads are not added
to the dataset or training cache. The framework may spool multipart data to a
temporary file, which the endpoint closes after processing.

The packaged artifact is a byte-for-byte copy of
`outputs/grouped/final/model.json`, SHA256
`4f5f84828fcb230b004a6721d82d9f9cc268298596404beab868a0f8f1da0a16`.
It contains the selected exponent and learned scale:

`D = exp(-20.4156106700493) × sum(count × (range/2)^5)`.

The runtime checks the extractor version and recording length. Responses carry
the artifact hash; a batch with different model versions cannot be exported.
Replacing the JSON after future validation is a deliberate release step, followed
by server restart. Training does not silently replace the deployed artifact.

The same inference class serves the command line:

```powershell
.venv/Scripts/python.exe Backend/SHM/predict.py --input Backend/SHM/dataset_shm/SHM/Test --output Backend/SHM/shm_predictions.csv
```

This uses `artifacts/model.json` by default. Use `--model PATH` to explicitly
choose a different compatible artifact. To rerun training and validation:

```powershell
.venv/Scripts/python.exe Backend/SHM/main.py all
```

See [README.md](README.md) for the training protocol and data requirements.

## Hackathon deliverables

The specification requires one app for the subsystems attempted, a demo video
no longer than three minutes, and a separate `predictions.zip`. Use this SHM page
to process the hidden test recordings and download the CSV. Put
`shm_predictions.csv` at the ZIP root alongside genuine outputs from any other
attempted subsystems. The automated score is computed from the submitted CSV;
the app and video demonstrate the working workflow.

The SHM CSV has exactly `file_id,prediction`, one row per original filename
including `.csv`. Display rounding does not affect exported precision. The
prediction is cumulative fatigue damage for that recording, not stress, a
percentage health score, failure probability, or remaining useful life. MAPE
requires reference labels; it cannot be measured for newly uploaded unlabelled
files. Existing Door UI still uses its own placeholder data; this change only
connects SHM to live inference.

Suggested video: open dashboard → select SHM → upload 16 test files → run →
show the completed table → download/open the CSV. Record this manually after
checking the team's other attempted subsystems.

Sources: [PS3 specification](https://raw.githubusercontent.com/aochinwen/NebulaX-Hackathon-ProblemStatement/main/PS3/01_Problem_Statement_3_Specifications.md),
[SHM information kit](https://raw.githubusercontent.com/aochinwen/NebulaX-Hackathon-ProblemStatement/main/PS3/03_References/SHM/SHM_Info_Kit.md).

## Git and deployment files

Commit the frontend changes, `.gitignore`, SHM Python source, tests,
requirements files, documentation, and **`Backend/SHM/artifacts/model.json`**.
The deployment needs `api.py`, `inference.py`, `data.py`, `models.py`, `splits.py`,
the artifact, and installed dependencies; keep them together. Other Python files
preserve reproducible training and validation.

Do not commit the raw dataset, `.cache`, `outputs`, generated prediction CSVs,
virtual environment, `node_modules`, or frontend build directory. These are now
ignored. Optional standalone model/code supporting material is separate from
the files needed to run your submitted app: the app deployment must still have
its model and inference code. Nothing has been pushed automatically.

## Verification

```powershell
.venv/Scripts/python.exe -m pytest Backend/SHM/tests -q
cd Frontend
npm run build
npm run lint
```

For a live browser check with the two servers running, install `playwright` in
the virtual environment and run `Backend/SHM/tests/browser_smoke.py` with that
Python. It uses installed headless Microsoft Edge by default (override channel
with `SHM_BROWSER_CHANNEL`), uploads the 16 local test files, downloads the actual
browser CSV, compares predictions, and checks malformed input, stale downloads
and drag/drop. Its screenshots and CSV are under ignored `outputs/app_smoke/`.
The API parity test needing the original dataset/saved reference predictions skips in a fresh
clone; synthetic mechanics and API rejection tests still run.
