# Nebula Hackathon — Door Subsystem Write-up

## Approach

`Train.csv`/`Test.csv` are continuous multi-cycle streams, not one row per example, so the
pipeline runs in two stages:

1. **Segmentation.** Within a cycle the stream samples at a rigid 20 ms; between cycles there are
   irregular multi-second idle gaps. Cycles are split at those gaps (threshold derived per-file
   from its own timing distribution, not hardcoded) rather than at command-flag transitions. This
   reproduces the answer key exactly: 110 Train / 38 Test cycles.
2. **Classification.** Each cycle's feature vector is compared to a per-operation (Open/Close)
   current threshold and labelled `Normal` or `Abnormal resistance`.

**Split:** no official one is given, and `Train.csv` is a single recording, so the split is
chronological — first 70% of cycles (77) to fit, last 30% (33) held out, cut only at a cycle
boundary. Chronological rather than random because `Test.csv` is a separate, later recording; a
shuffled split would leak adjacent-in-time cycles across the boundary.

## Feature engineering

Abnormal resistance makes the motor draw more current to keep moving. The inrush and braking
phases are dominated by motor dynamics, not track resistance, so the diagnostic window is the
**mid-travel, steady-state** portion of the stroke (20th–85th percentile of travel). That window is
located by **travel fraction** — leaf position rescaled 0–1 over each cycle's own range/direction —
so cycles that run long or overshoot still get their steady-state phase measured correctly.

~33 features per cycle: distributional stats (mean/median/std/max/p90/p75) of current, voltage,
EMF — whole-cycle and mid-travel; current/power normalised by EMF (cancels door-to-door supply
voltage differences, per the info kit); and shape descriptors (duration, row count, travel range,
current AUC). The model's actual decision feature is **`current_mid_mean`**, which separates the
two classes by 19–54 standard deviations.

## Model selection

Five candidates, identical 5-fold stratified CV plus a stricter leave-one-time-block-out CV (no
door/car identifier exists to group by, checked explicitly): median+k·MAD per-operation threshold,
the older min/max-midpoint threshold, logistic regression, gradient boosting, random forest.

All five reached macro-F1 ≥ 0.96; the MAD threshold and midpoint threshold tied at 1.0000 on both
CV schemes. Chose the **MAD threshold**: it anchors the cut to the Normal cluster's median/spread
rather than the single nearest Abnormal point — the midpoint rule swung 60 mA and missed a fault
when one training fault was withheld during the leakage audit. Per-operation thresholds (Open
304.2 mA, Close 251.3 mA) because Open/Close have different current profiles. Exported as plain
JSON, so inference needs no scikit-learn.

## Metrics, and why

Official metric — **IoU-weighted F1** matching predicted segments to true ones by label and time
overlap (Door Info Kit §4) — is what's implemented and reported throughout, not a proxy like
accuracy.

On the untouched holdout (33 cycles): all recovered exactly, all labels correct, IoU-weighted F1 =
**1.0000**. CV macro-F1 is reported both stratified (shuffled, optimistic) and time-blocked
(stricter) so a perfect score reads as measured, not assumed — both 1.0000. Abnormal-class recall
is tracked separately since only 19/110 cycles are abnormal and that's the costly class to miss.

## Assumptions and disclosed limitations

- **No official split** → chronological cut at a cycle boundary, simulating `Test.csv` as a later
  recording rather than a random sample.
- **No door/car identifier in the data** (`Car Type`/`Car Number`/`Door Number` are documented but
  absent from both files — verified, not assumed) → leave-one-door-out is impossible;
  leave-one-time-block-out CV is reported as the closest substitute, not an equivalent.
- **Mid-travel window and `current_mid_mean` were chosen by hand** after inspecting the full
  training set, not inside CV — a mild researcher-degrees-of-freedom leak. Unlikely to matter given
  19–54σ class separation, but disclosed rather than hidden.
- **`travel_fraction`'s design was informed by unlabelled Test inputs** (an out-of-range Open cycle
  only seen in `Test.csv` prompted it). No labels were ever available, and the design is correct on
  its own merits, but seeing the input distribution ahead of time is a real, if mild, information
  flow.
- **The faults here aren't "slight."** The mildest fault sits 25–63% above the Normal range, easier
  than the "slight resistance fault" case the problem statement frames as the core difficulty. A
  perfect score means the present faults were separable, not that marginal faults would be caught.

## File structure (`Backend/Door/`)

```
Door/
├── main.py               CLI entry point: train / predict / evaluate / verify / check
├── predict.py             Thin wrapper the app calls (--input / --output)
├── requirements.txt       inference deps (pandas, numpy) vs. training-only (scikit-learn, joblib)
├── core/                  shared by training + prediction
│   ├── data.py               CSV loading, cycle segmentation, chronological split
│   ├── features.py           per-cycle feature extraction (travel_fraction, FEATURE_COLUMNS)
│   ├── classifier.py         loads door_model.json, applies the threshold (sklearn-free)
│   ├── scoring.py            official IoU-weighted F1 metric
│   └── errors.py             catchable DoorInputError / DoorModelError
├── training/              fits the model (needs scikit-learn, runs under WSL)
│   ├── train.py               builds features, 5-fold CV over 5 candidates, selects + exports
│   ├── evaluate.py            scores the frozen model on the untouched holdout
│   ├── test_metrics.py        unit tests vs. the info kit's worked metric examples
│   └── validate_segmentation.py   checks segmentation matches Train_Segments_Answer.csv exactly
├── prediction/            produces + validates submissions (numpy/pandas only, native Windows)
│   ├── predict.py             stream in → segments + labels out, plus runtime guards
│   └── verify_submission.py   checks a door_predictions.csv before it's zipped up
├── audit/                 read-only leakage/robustness checks, write nothing
│   ├── check_identifier_columns.py   confirms door/car columns are absent, not constant
│   ├── grouped_cv.py                 leave-one-time-block-out CV
│   ├── permutation_test.py           shuffled-label CV sanity check
│   ├── threshold_k_sweep.py          sweeps k in median + k·MAD
│   └── dataset_limitations.md        write-up of what the audits found
├── model/                 training output, loaded at runtime
│   ├── door_model.json        portable model (no sklearn needed)
│   ├── door_model.joblib      full pickled estimator, reference only
│   ├── door_reference.json    duration/current envelopes for runtime guards + UI
│   └── training_report.json   CV results, thresholds, margins
└── output/                generated by predict.py
    ├── door_predictions.csv   submission schema: start_time, end_time, prediction
    └── door_detail.csv        per-cycle detail for the app's UI
```

`training/` needs scikit-learn (WSL, since Smart App Control blocks its Windows binaries);
everything else needs only numpy/pandas, since `train.py` exports fitted thresholds as plain JSON
rather than shipping the pickle.
