# SHM fatigue modelling and validation

One complete stress CSV is one independent labelled modelling unit. This pipeline
preserves raw stress magnitudes, extracts rainflow amplitudes (`range / 2`), and
evaluates compact fatigue models with file-level cross-validation. No filename,
window identifier, or timestep is a predictor.

## Run

From the repository root in PowerShell:

```powershell
.venv/Scripts/python.exe -m pip install -r Backend/SHM/requirements.txt
.venv/Scripts/python.exe Backend/SHM/main.py audit
.venv/Scripts/python.exe Backend/SHM/main.py develop
.venv/Scripts/python.exe Backend/SHM/main.py final
```

`python Backend/SHM/main.py all` runs all three stages. Defaults resolve relative
to the script, so the working directory does not affect the dataset location.
Use `--data PATH` for a directory containing `Train/`, `Test/`, and
`Train_Labels.csv`. Each training/test signal must be headerless, single-column,
finite float64 data with exactly 581,120 rows. Inventory mismatches fail loudly.

The first run extracts all 80 signals. Later runs reuse content-addressed,
label-free caches in `.cache/`. File content, extractor version, and expected
length determine the cache key. No smoothing, normalisation, clipping,
detrending, binning, or dropping endpoint half cycles is performed.

Run tests with:

```powershell
.venv/Scripts/python.exe -m pytest Backend/SHM/tests -q
```

In Colab, place this SHM directory in the runtime or mounted Drive, install
`requirements.txt`, and run the same commands with `python` and an explicit
`--data` path. For example:

```python
%pip install -r /content/nebula-hackathon/Backend/SHM/requirements.txt
!python /content/nebula-hackathon/Backend/SHM/main.py all --data /content/SHM --output /content/shm_results --cache /content/shm_cache
```

## Candidate models and frozen protocol

The default pool has 162 candidates:

- Ordinary median and MAPE-optimal weighted median.
- Stress standard-deviation power law, powers 1 through 8 in steps of 0.5.
- `D = K Q_m`, exponents 1 through 12 in steps of 0.25.
- `D = A Q_m^beta`, the same exponents, beta 0.75 or 1.25. Beta 1 is the
  preceding physics family.
- Nonnegative `K1 Q_3 + K2 Q_5`, fitted by relative absolute-error linear programming.
- Nine small Ridge models: m in {3, 5, 7}, penalty in {1, 10, 100}. Features are
  log fatigue moment, log cycle count, log(a95/a50), log(amax/a95), and
  damage-weighted cycle mean stress. Quantiles use cycle-count weights.

The constant and multiplicative physics scales minimise training MAPE exactly
through weighted medians. Small Ridge models fit log damage, then calibrate a
positive multiplier for training MAPE. All scaling and calibration happen inside
the relevant training partition. Log-moment accumulation avoids power overflow.

Residual correction is disabled by default. To evaluate it only after finding
reproducible residual structure, use a new output directory:

```powershell
.venv/Scripts/python.exe Backend/SHM/main.py all --include-hybrid --hybrid-reason "Describe the residual evidence here" --output Backend/SHM/outputs/hybrid_experiment
```

This adds nine fixed-configuration Ridge corrections using breadth, tail ratio,
and damage-weighted mean stress. Their target is the four-fold cross-fitted log
ratio of true damage to base prediction. The correction multiplies the physics
prediction through exp(g). Base m and correction penalty are candidate settings,
selected within CV; no globally selected base or residual table is reused.

`protocol.json` records the full candidate set and seeds. To shortlist models,
copy it elsewhere, edit only its candidate list (retain both baselines), and pass
`--protocol FILE` to a **new** output directory. `frozen_protocol.json` binds this
configuration to training hashes, labels, and groups before evaluation starts.
An incompatible rerun cannot silently overwrite the frozen run. Rerunning the
same procedure/data is allowed. Development does not silently alter final candidates.

## Validation

- Development: 5 folds x 5 repeats, four target-quantile strata when feasible.
  Compare each fixed candidate on the same splits. Winning development results
  are exploratory, not an unbiased final performance claim.
- Final: 5 outer folds x 5 repeats; one 4-fold inner loop selects **family and
  configuration**. Outer labels do not determine that fold's selection or fit.
- Sensitivity: 3 prespecified unbalanced outer 5-fold repeats, with the same
  inner selection procedure. Report separately rather than selecting whichever
  splitting strategy looks better.
- Selection: retain candidates within 0.01 absolute MAPE of the best, then choose
  the lowest complexity, then lowest MAPE, then name for exact ties. Complexity:
  constants < stress/physics < flexible/two-moment < small Ridge < hybrid.
- Refit: independently apply that rule using 5-fold x 5-repeat CV on all 64
  files, then train once on all labels. Outer winners are not voted into the final
  fit. The refit-selection score is not a test estimate.

Inner quantiles are computed only from the outer training labels. Equal targets
stay together in the same target bin; if bins are too small, use shuffled KFold.
Group integrity always overrides stratification. If waveform groups are present,
both the primary and sensitivity runs use group splits with different fixed
seeds; the latter is then an alternate-group-split check, not a comparison of
target stratification. Split CSVs record validation
membership; training membership is its complement in the enclosing partition.

### Dependence checks

Exact duplicate files and sparse content-anchored 512-sample matching subsequences
are reported. Unlike fixed-position hashing, content anchors can detect shifted
exact overlaps. Connected matches are conservatively grouped before CV. This
screening is not exhaustive and cannot certify independent acquisition sessions.

The full-data waveform audit additionally screens every pair at stride 64, then
checks candidate pairs using all observations. It conservatively groups pairs
with absolute full-signal correlation at least 0.99 and sign-consistent
correlation at least 0.95 in each of eight contiguous blocks. The initial
screening threshold is 0.985. All thresholds are label-free, but these remain
inferred waveform-dependence groups, not proven acquisition sessions. They are
combined with exact-match and supplied metadata groups through connected components.
First-difference correlations are also reported for inspection. The audit found
high waveform similarities missed by exact hashes, so group-preserving results
are the primary results for the supplied dataset.

Supply known acquisition groups as `--groups groups.csv`, with exactly one
`filename,group` row for each training file. Known groups and exact-overlap groups
are combined. Every outer, inner and residual cross-fit respects them. Fold count
reduces if there are fewer groups; with too few independent groups to nest, the
pipeline stops instead of silently leaking. Group-aware bootstrap resamples
whole groups and preserves file weighting.

`nearest_neighbors.csv` uses standardised file summaries for descriptive
inspection only. Similar amplitude distributions are not automatically sessions
and are never used as model-selection groups.

## Outputs

All current default reports live in `outputs/grouped/` (ignored by Git). The
earlier random-file results under `outputs/` are retained as historical sensitivity
results; they preceded the full waveform dependence check.

| Path | Contents |
|---|---|
| `audit/audit.json` | Input checks, units/independence limitations, counts |
| `audit/features.csv` | All per-file raw and rainflow summaries, moments, labels |
| `audit/overlaps.csv` | Exact overlap evidence with positions |
| `audit/nearest_neighbors.csv` | Candidates for waveform/provenance review |
| `audit/waveform_similarity_checks.csv` | Coarse lag correlations for six nearest summary pairs; not inferred sessions |
| `audit/correlated_waveforms.csv` | All screened pairs with full-resolution and blockwise correlation evidence |
| `development/` | All candidate OOF results, fit parameters, saved splits |
| `final/balanced/` | Nested evaluation of the complete selection procedure |
| `final/unbalanced_sensitivity/` | Separate nested sensitivity run |
| `final/model.json` | Portable final model, versions and protocol fingerprint |
| `final/shm_predictions.csv` | Exactly 16 positive finite test predictions |
| `final/test_support_flags.csv` | Test summaries outside training min/max |

Each validation report includes pooled MAPE, score, per-file/repeat/fold errors,
target-quartile errors, worst files, residual correlations by repeat, and
conditional bootstrap sensitivity intervals. Development includes paired
file-level differences versus the weighted-median baseline. Nested reports also
include inner candidate scores, selected parameter values and family frequencies.

Primary MAPE averages absolute percentage errors over file-repeat appearances;
each file contributes equally. Fold scores are not clipped before pooling. The
MAPE of averaged repeated OOF predictions is explicitly a separate diagnostic.
There remain 64 files, not 320 independent observations. Bootstrap intervals
resample file/group identities, keeping repeats together; they are conditional
on the existing OOF predictions and omit refitting uncertainty. Repeat SD is
split sensitivity, not a standard error.

Residual correlations are exploratory. New seeds or rerunning CV cannot erase
label reuse when residuals inspire new features. Frozen nested selection is a
practical internal evaluation, not an untouched external test. Material units,
sampling frequency, original acquisition groups, organiser corrections, and the
previous modelling implementation remain unverified. No historical bug is inferred.

## Inference without labels

```powershell
.venv/Scripts/python.exe Backend/SHM/predict.py --model Backend/SHM/outputs/grouped/final/model.json --input Backend/SHM/dataset_shm/SHM/Test --output Backend/SHM/shm_predictions.csv
```

Inference requires only the saved JSON model, code/dependencies and input signal
files. It never reads training labels. It uses the same feature extractor and
rejects schema/version mismatches and nonpositive/nonfinite predictions rather
than silently clipping them. The output contains only `file_id,prediction`.
