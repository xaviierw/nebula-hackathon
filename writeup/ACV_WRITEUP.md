# ACV Fault Localisation

## Problem and objective

The ACV task is a fault-diagnosis and localisation problem. Given one train-car operational export, the system must identify which car is most likely to have a refrigerant leak. The required submission is not a binary fault label: it is a complete ordering of every car in the file, from most to least likely to be faulty.

The output is written as `acv_predictions.csv` with two columns:

```text
file_id,ranked_cars
```

`ranked_cars` preserves the car identifiers exactly as they appear in the source headers and joins them with `|`.

## Approach

The model uses a peer-relative, two-signal heuristic. This is appropriate for the available task because the faulty car is expected to stand out against other cars operating in the same train and recorded under the same environmental conditions.

### 1. Input validation and cleaning

The pipeline accepts CSV and Excel exports. It standardises common ACV header variants into a consistent internal schema, including:

- ambient temperature;
- indoor/cabin temperature;
- cooling setpoint;
- running mode; and
- information-valid status.

Rows marked `Invalid` are treated as missing values. Temperature and setpoint fields are converted to numeric values. Cooling calculations are restricted to valid readings and cooling modes such as Automatic Cooling, Full Cooling, and Half Cooling.

The input is rejected when it is empty, lacks indoor-temperature columns, or appears to be a rich telemetry format outside the expected operational export schema.

### 2. Train-level ambient reference

For each timestamp, the pipeline calculates a train-level ambient reference as the median of the populated car/end ambient sensors. This reduces the effect of one noisy ambient sensor and gives every car a common environmental reference.

An adaptive demand threshold is then calculated from the 50th percentile of the train ambient reference. The model focuses its scoring on the warmer, higher-demand half of the recording. This avoids treating low-demand periods as equally informative when air-conditioning faults are harder to distinguish.

### 3. Peer-relative shortfall signal

For each car, the pipeline calculates:

$$
\text{shortfall}_{c,t} = \text{indoor}_{c,t} - \text{setpoint}_{c,t}
$$

At each timestamp, it subtracts the median shortfall across the train:

$$
\text{relative shortfall}_{c,t} = \text{shortfall}_{c,t} - \operatorname{median}_{j}(\text{shortfall}_{j,t})
$$

A car with a persistently larger positive shortfall is running warmer than its peers relative to its requested cooling setpoint, which is consistent with reduced cooling performance.

### 4. Delivered-cooling signal

The second signal measures how much cooling each car appears to deliver relative to the common ambient reference:

$$
\text{delivered cooling}_{c,t} = \text{ambient reference}_{t} - \text{indoor}_{c,t}
$$

The model compares each car's delivered-cooling value with the train median during high-demand periods. A car delivering less cooling than its peers receives a stronger fault score.

This second signal is deliberately different from setpoint shortfall. Using both helps avoid relying on one measurement relationship alone:

- shortfall asks whether the car is missing its requested indoor target;
- delivered cooling asks whether the car is removing less heat than its peers.

### 5. Borda rank fusion

Each signal independently ranks the cars. The model converts each ranking into Borda points and adds the points across the two signals. The combined order is the final ACV prediction.

This choice is conservative and interpretable. It avoids assuming that the two signals have comparable units or that one raw temperature difference should dominate the other. It also preserves the required ordering output even when the two signals disagree.

The API reports a warning when the two signals select different top cars. That warning is an invitation to review the result with maintenance records, not a claim that the model has proven or disproven a refrigerant leak.

## Model selection and rationale

A peer-relative heuristic with rank fusion was selected instead of a supervised classifier because the required output is an ordering, the input is naturally multi-car and relational, and the available repository data does not establish a sufficiently broad independent training set for a high-capacity model.

The method has four practical advantages:

1. **It matches the task output.** The competition scores the position of the true faulty car, so producing a ranking directly is preferable to converting class probabilities into an arbitrary order.
2. **It uses the train as its own control group.** Cars recorded at the same time provide a useful comparison under shared ambient conditions.
3. **It is interpretable.** Engineers can inspect the two component signals and understand why a car was prioritised.
4. **It is robust to scale differences.** Borda fusion combines ordering evidence rather than requiring the two features to be calibrated to the same numerical scale.

## Metrics and validation

### Official metric

The specification defines the ACV leaderboard metric as a **linear rank-decay score**. The score rewards placing the true faulty car first and gives partial credit when it is placed nearby. This is the correct primary metric because ACV is a ranking/localisation task rather than a binary classification task.

Accuracy of only the first-ranked car is useful as a simple engineering diagnostic, but it is not sufficient as the headline metric: it treats ranks 1 and 2 as completely different outcomes and ignores the value of a near-correct ranking.

The project should report the official rank-decay score on a held-out validation split before submission. The exact formula should be taken from the ACV Info Kit/evaluator distributed with the challenge. That Info Kit is not present in this repository, so this write-up does not claim an official score that cannot be reproduced here.

### Supporting diagnostics

The app exposes additional interpretability information for each prediction:

- the top-priority car;
- the number of cars included in the ranking;
- the rank-separation score gap between first and second place; and
- whether the two component signals agree on the top car.

The rank-separation value is a relative Borda-score gap, not a probability, confidence interval, or statistical significance test. It should be used to identify close rankings that deserve joint inspection, not as a calibrated certainty measure.

For validation, predictions should be generated for complete files that were not used to tune the heuristic. A file-level split is preferred because rows from the same recording share operating conditions and are not independent examples. Splitting rows from one workbook across train and validation would leak the recording's operating context and overstate generalisation.

## Assumptions and limitations

- The car identifiers are encoded in the source column headers and are preserved exactly in the output.
- Cars in the same export are treated as peer comparators exposed to broadly shared ambient conditions.
- Higher cabin-to-setpoint shortfall and lower delivered cooling are treated as evidence of weaker cooling performance, not direct proof of a refrigerant leak.
- The 50th-percentile ambient threshold is a pragmatic default for identifying higher cooling demand. It should be tuned only using file-level validation, not the held-out test file.
- Missing or invalid sensor readings are excluded from the relevant calculation. If the input does not contain enough usable car telemetry, the upload should fail clearly rather than produce a misleading ranking.
- The model does not estimate a causal refrigerant leak rate and does not replace maintenance inspection.
- A disagreement warning is evidence of model uncertainty between the two ranking views; it is not a formal statistical test.

## Reproducibility

CLI prediction for one file:

```powershell
cd Backend\ACV
..\..\.venv\Scripts\python.exe main.py predict --input prediction\Test\acv_test_case.xlsx
```

The same `predict_file()` seam is used by the web API. The API runner and CLI load the shared model artifact at `Backend/model/acv_model.json`, so the two interfaces are intended to produce identical rankings for identical files.
