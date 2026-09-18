# Completed SHM validation run

The selected model is the amplitude-based rainflow fatigue law:

\[
\widehat D = 1.3602318550841202\times10^{-9}
\sum_j n_j (R_j/2)^5.
\]

The final calibration uses all 64 labelled files. These are effective fitted
parameters; unknown stress units and organiser corrections prevent interpreting
them as recovered material constants.

| Evaluation | Pooled MAPE | Score |
|---|---:|---:|
| Group-preserving nested CV, 5 folds x 5 repeats | 0.025896 | 0.974104 |
| Alternate group splits, nested 5 folds x 3 repeats | 0.025961 | 0.974039 |
| Development weighted-median baseline | 0.570252 | 0.429748 |
| Development ordinary-median baseline | 0.936352 | 0.063648 |

Every outer fold selected `physics_m5`. The default search compared 162
prespecified candidates, with a 0.01 absolute-MAPE simplicity preference applied
inside each outer training set. The two-moment model gave essentially the same
predictions and did not justify its additional coefficient. The hybrid remains
disabled. No additional search was performed after inspecting these results.

For the primary nested run, repeat MAPE ranged from 0.025508 to 0.026727
(SD 0.000496). The conditional group-bootstrap sensitivity interval was
approximately [0.019357, 0.033847]. It does not include refitting uncertainty and
is not a guaranteed confidence interval for the hidden-test score.

## Dependence audit changed the validation design

All 80 files passed schema, length and finiteness checks. Exact hashes found no
duplicates. Full-waveform comparisons nevertheless found 15 pairs with high
correlation, producing 56 conservative training groups from 64 files. Several
pairs span training and test files.

The grouping rule uses no labels: absolute full-signal correlation at least 0.99,
with sign-consistent correlation at least 0.95 in each of eight contiguous blocks,
after a stride-64 prescreen at 0.985. Connected pairs remain together throughout
outer splits, inner selection and residual cross-fitting. Bootstrap resampling
also keeps groups intact. These are inferred waveform-dependence groups, not
verified acquisition sessions; other dependencies may remain undetected.

Because group integrity overrides target stratification, the two current nested
runs compare different group-split seeds. Their directory names `balanced` and
`unbalanced_sensitivity` retain the protocol labels, but neither splits related
waveforms to obtain target balance.

The original random-file nested result (MAPE 0.025835) remains under `outputs/`
as historical sensitivity evidence. **Use `outputs/grouped/` for the current
model and primary results.**

## Deliverables and verification

- `shm_predictions.csv`: 16 unique test filenames with positive finite predictions.
- `outputs/grouped/final/model.json`: portable final model and protocol fingerprint.
- `outputs/grouped/final/balanced/`: primary OOF predictions, scores, uncertainty,
  selected parameters, residual diagnostics and split membership.
- `outputs/grouped/audit/`: features, overlap evidence and waveform checks.
- `README.md`: commands for local use, Colab and label-free inference.

All 20 automated tests passed. Additional checks verified actual saved inner/outer
group boundaries, OOF coverage, metric pooling and final artifact provenance.
Standalone inference reproduced the final predictions without training labels.

These are internal CV estimates, not hidden-test scores. Adaptive development
reuse, inferred groups and the small dataset remain limitations. The previous
implementation was unavailable, so no historical implementation bug is claimed.
