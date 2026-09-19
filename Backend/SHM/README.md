# SHM subsystem

**Status: not built.** This directory is a skeleton. You own it.

Regression -- cumulative fatigue damage estimation.

**Signal:** Dynamic stress time series.

---

## Before you write any code

Read this subsystem Info Kit in `Backend/03_References/SHM/`. The problem
statement (section 2.2) calls it *"the authoritative problem definition"* --
the summary table is only a sketch, and the scoring metric you will be judged
on is specified there in section 4, with a worked example.

> **Blocker:** `Backend/02_Datasets/SHM/` and `Backend/03_References/SHM/`
> do not exist in this repo yet. Only `Door/` is present. You need the original
> hackathon material before you can start on features.

---

## Submission format

`shm_predictions.csv`

```
file_id,prediction
```

`prediction` is a single numeric cumulative-damage value. One row per file.

Source: `Backend/01_Problem_Statement_3_Specifications.md` section 4.1.

---

## What you need to deliver

Fill in the skeleton:

```
SHM/
  core/data.py             column constants, read_raw(), check_schema()
  core/features.py         feature extraction
  core/model.py            load + predict
  core/errors.py           already written -- ShmInputError / ShmModelError
  training/train.py        fits, selects, writes ./model artifacts
  training/evaluate.py     scores against the info kit fixed metric
  prediction/predict.py    <- THE ONE FILE THE API CALLS
```

### The only signature that is not yours to choose

```python
# prediction/predict.py

def predict_file(frame: pd.DataFrame, model, reference: dict | None = None) -> dict:
    ...
```

Returning, for this subsystem:

```python
{"prediction": 0.0421, "interval": [0.031, 0.055], "warnings": []}
```

Three rules, all learned the hard way on Door:

1. **Raise, never `sys.exit`.** Use `ShmInputError` / `ShmModelError` from
   `core/errors.py`. `SystemExit` inherits from `BaseException`, so a caller
   `except Exception` misses it and the whole server dies instead of showing
   the message.
2. **`ShmInputError` messages are shown to users verbatim.** Write them for a
   non-technical reader. Multi-line is fine.
3. **Return plain `int` / `float` / `str`.** `np.int64` is not a subclass of
   `int`, and the API response validation rejects it.

Keep `predict_file` deterministic. The API caches results by file hash and
will not re-run your model on a file it has already seen.

---

## Wiring it into the API

When `predict_file` works, it is a **two-file change** and you write no routes:

1. Fill in `Backend/app/subsystems/shm/runner.py` -- copy
   `Backend/app/subsystems/door/runner.py`, which is the worked reference.
2. In `Backend/app/subsystems/registry.py`, replace

   ```python
   register(NotImplementedRunner("shm", "SHM"))
   ```
   with
   ```python
   register(ShmRunner())
   ```

Auth, the shared prediction cache, per-user history and error mapping all come
for free. Confirm it worked:

```bash
curl.exe http://127.0.0.1:8000/api/health
```

Your subsystem should report `"available": true` with a real `model_version`.

> **Import-name collision.** Door currently occupies the top-level module names
> `core`, `training` and `prediction` via its `vendor_path.py` shim. The second
> subsystem wired into the API **cannot** reuse those names. Give this
> directory a package root, or rename its modules to `shm_core` /
> `shm_prediction`, before you wire up. See `Backend/README.md`.

---

## Running it standalone

```bash
cd Backend/SHM
python main.py train
python main.py predict --input <a test file>
python main.py evaluate
```

Artifacts go in `./model/`, predictions in `./output/`. Both are gitignored --
everything in them must be reproducible from `training/train.py`.
