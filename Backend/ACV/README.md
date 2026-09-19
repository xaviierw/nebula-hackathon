# ACV subsystem

**Status: connected to the shared API.**

ACV ranks every train car from most to least likely to have an air-conditioning
fault. It uses cabin temperature, ambient temperature, cooling setpoint,
running mode and validity telemetry.

The deployed artifact is a deterministic peer-relative heuristic rather than a
fitted scikit-learn estimator. The original training recordings and ACV info kit
are not committed, so this clone can reproduce inference but cannot independently
reproduce or verify the model's hackathon score.

## Accepted input

- Standard 67-column ACV operational exports.
- CSV, XLSX or legacy XLS.
- At least two cars with indoor temperature, cooling setpoint, running mode and
  validity fields, plus outdoor temperature telemetry.
- At least one usable cooling observation for every ranked car.
- Maximum file size: 25 MiB.

The representative runtime example is
`prediction/Test/acv_test_case.xlsx`.

## Submission format

`acv_predictions.csv` contains exactly:

```csv
file_id,ranked_cars
```

There is no `prediction` column. `ranked_cars` lists every car from most to
least likely faulty, preserves the identifier used in the source headers (for
example `03`, not `Car 3`), and joins identifiers with `|`.

## Runtime design

```text
ACV/
  core/data.py             reads and validates CSV/Excel telemetry
  core/features.py         calculates peer-relative cooling metrics
  core/model.py            combines the two rankings with Borda count
  prediction/predict.py    pure DataFrame-to-result API seam
  training/train.py        writes the deterministic configuration artifact
  training/evaluate.py     reports top-ranked accuracy when training files exist
```

The shared adapter is `Backend/app/subsystems/acv/runner.py`. It inherits
Firebase authentication, Firestore caching, upload limits, history and error
mapping from the generated subsystem router. Its model version includes an
explicit pipeline revision so feature changes invalidate cached predictions.

The success response is:

```json
{
  "ranked_cars": ["03", "01", "02"],
  "scores": {"03": 0.91, "01": 0.67, "02": 0.42},
  "warnings": []
}
```

Bad files raise `AcvInputError` with an end-user-readable message. Missing or
invalid server artifacts raise `AcvModelError`. Uploaded bytes are processed in
memory and are never persisted.

## Commands

From `Backend/ACV`:

```bash
python main.py train
python main.py predict --input prediction/Test/acv_test_case.xlsx
python main.py evaluate
```

`train` rebuilds the deterministic JSON configuration. `evaluate` deliberately
returns a non-zero status when the omitted training recordings are unavailable;
it does not report a misleading `0/0` success.

From `Backend`, run the shared API with:

```bash
../.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Then confirm `/api/health` reports ACV as available.
