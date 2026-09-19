# SHM Cumulative Fatigue-Damage Estimation

We predict one cumulative fatigue-damage value per stress recording using a
physics-informed regression model trained on 64 labelled files. Each CSV contains
581,120 finite stress observations. Raw signed values are preserved without
smoothing, normalisation, clipping or downsampling; filenames are identifiers only.

Rainflow counting converts cycle ranges to amplitudes (`R/2`), retaining full
cycles (`n = 1`) and endpoint half cycles (`n = 0.5`). Fatigue moments
`Q_m = sum_j n_j (R_j/2)^m` are accumulated in log space for numerical stability.
Alternative models also considered stress statistics, cycle counts, amplitude
distribution features and cycle mean stress.

We compared 162 candidate configurations, including constant baselines, power
laws, two-moment models and regularised regression. Selection favoured the
simplest model within one percentage point of the lowest validation MAPE.
Every outer fold selected the fifth-power fatigue law. Calibrated on all 64
labelled recordings, the deployed model is:

`D_hat = 1.3602318550841202e-9 * sum_j n_j (R_j/2)^5`

This compact model provides interpretable cycle contributions without the
complexity of a high-capacity model.

Validation used five outer folds repeated five times, with four-fold inner model
selection. A label-free waveform audit produced 56 conservative training groups;
related recordings stayed together in all folds, and calibration used training
partitions only.

We report the prescribed MAPE and score `max(0, 1 - MAPE)`. MAPE measures error
relative to each recording's true damage, allowing comparison across damage scales.

| Internal evaluation | MAPE | Score |
| --- | ---: | ---: |
| Grouped nested cross-validation | 2.5896% | 0.974104 |
| Alternative group splits | 2.5961% | 0.974039 |

These are internal estimates, not accuracy, confidence or confirmed hidden-test
scores. Waveform groups approximate acquisition dependence; unknown dependencies,
the small dataset and development reuse limit generalisation. With stress units
and organiser corrections unverified, fitted parameters are effective calibration
values rather than recovered material constants.

The shared web app uses the same inference logic as the CLI and exports one
`file_id,prediction` row per recording. Outputs estimate recording-level fatigue
damage, not remaining useful life or structural fault status.
