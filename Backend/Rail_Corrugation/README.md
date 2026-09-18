# Rail Corrugation

I classify one-second sensor recordings as **Normal**, **Side I**, or **Side II** corrugation. My selected model is **Extra Trees with 15 vibration-time features**, achieving **0.813 ± 0.122 validation Macro F1**. The full analysis is in [Rail_Corrugation.ipynb](Rail_Corrugation.ipynb).

## Process and feature engineering

1. **Inspect the data:** 272 labelled recordings—234 Normal, 14 Side I, and 24 Side II. All passed the input checks. Fault recordings generally had higher estimated speeds, highlighting a possible shortcut for the model.
2. **Summarise each recording:** extract 69 candidate features covering speed, vibration/shock statistics, frequency content using Welch power spectra, and side-to-side log ratios.
3. **Compare models:** use identical stratified five-fold splits repeated five times. Logistic Regression uses scaling fitted within each training fold. Logistic Regression and Extra Trees use balanced class weights; no recordings are duplicated or discarded.
4. **Refine and finalise:** increase Extra Trees' `max_features` from `"sqrt"` to `0.75`, then fit the selected model on all 272 labelled files. Official Test files are excluded from training.

The final **15 features** are:

- **Six vibration summaries per side:** median, 90th-percentile, and maximum RMS; maximum absolute peak; median kurtosis; and 90th-percentile crest factor.
- **Three side-to-side log ratios:** 90th-percentile RMS, maximum RMS, and maximum absolute peak.

These describe vibration magnitude, spikiness, and differences between the rails. The final model excludes explicit speed, shock, and frequency-domain inputs.

## Baselines and results

**Macro F1** averages the three class-specific F1 scores equally, so the many Normal examples cannot dominate the metric. It is not accuracy. Scores below are the mean ± standard deviation across 25 validation folds, not confidence intervals.

| Model | Features | Validation Macro F1 |
|---|---|---:|
| Always predict Normal | No meaningful signal information | 0.308 ± 0.002 |
| Logistic Regression | Speed only | 0.441 ± 0.058 |
| Logistic Regression | 15 vibration-time features | 0.715 ± 0.094 |
| Original Extra Trees | 15 vibration-time features | 0.766 ± 0.090 |
| Logistic Regression | 67 vibration/shock features | 0.759 ± 0.092 |
| **Refined Extra Trees** | **15 vibration-time features** | **0.813 ± 0.122** |

The selected model uses **250 trees**, `max_features=0.75`, `min_samples_leaf=2`, balanced class weights, and seed 42. It is saved in `models/rail_corrugation.joblib`; prediction applies the same feature extraction before using the classifier.

Standalone inference is in [predictor.py](predictor.py): `predict_file(path)` returns a filename and label; `predict_files(paths)` returns a `file_id,prediction` table in input order. It computes the 15 selected features and caches the model between calls. [requirements.txt](requirements.txt) pins the model's dependencies, and [tests/test_predictor.py](tests/test_predictor.py) checks notebook parity, standalone prediction, invalid inputs, and batch behaviour. The saved model must accompany the predictor when shared; it is not excluded by the current Git ignore rules.

A separate fixed-five-fold evaluation produced **Macro F1 0.851**: Normal **0.981**, Side I **0.714**, and Side II **0.857**. It recorded **12 mistakes**, compared with 20 for the original Extra Trees baseline. This is a different validation summary, not an official Test score.

## Main findings and limitations

The compact vibration-based model was the strongest tested combination; the broader feature set did not automatically improve performance. **Side I remains the weakest class.**

Few fault examples make scores variable. Vibration can still encode speed even without a speed input, and missing run/session identifiers prevent ruling out related recordings across folds. Because EDA and model selection reused these labelled recordings, all reported scores are **development estimates**, not independent test performance or a safety guarantee.
