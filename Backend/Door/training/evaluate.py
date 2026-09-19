"""Score the frozen pipeline end-to-end on the untouched holdout.

This is the honest estimate of Test performance: the holdout slice of Train.csv
is fed in as a *raw stream*, so segmentation errors are included in the score,
not just label accuracy. Nothing here fits anything -- the model is loaded as
trained on the fit split alone.
"""

from __future__ import annotations

from core.classifier import DoorClassifier, to_segments
from core.data import DATA_DIR, chronological_split, find_cycles, load_stream, load_truth
from core.features import build_table
from core.scoring import ABNORMAL, score_segments

train_stream = load_stream(DATA_DIR / "Train.csv")
truth = load_truth(DATA_DIR / "Train_Segments_Answer.csv")
fit_frame, fit_truth, hold_frame, hold_truth = chronological_split(train_stream, truth)

classifier = DoorClassifier.load()
print(f"Model: per-operation threshold on '{classifier.feature}'")
print(f"  Open  cycles flagged above {classifier.threshold_open:.1f} mA")
print(f"  Close cycles flagged above {classifier.threshold_close:.1f} mA")
print(f"  Fitted on: {classifier.spec['fitted_on']}\n")


def run(name: str, frame, expected) -> None:
    """Run the full pipeline over a raw stream slice and score it."""
    cycles = find_cycles(frame)
    table = build_table(frame, cycles)
    labels = classifier.predict(table)
    predicted = to_segments(table, labels)
    result = score_segments(expected, predicted)

    n_abnormal_true = sum(1 for s in expected if s.label == ABNORMAL)
    n_abnormal_pred = sum(1 for s in predicted if s.label == ABNORMAL)

    print(f"--- {name} ---")
    print(f"  cycles found: {len(predicted)} (truth has {len(expected)})")
    print(f"  abnormal: predicted {n_abnormal_pred}, actual {n_abnormal_true}")
    print(f"  {result.summary()}")

    # Label-level errors, since IoU here is perfect and all error is labelling.
    by_time = {s.start: s.label for s in expected}
    wrong = [
        (p.start, by_time[p.start], p.label)
        for p in predicted
        if p.start in by_time and by_time[p.start] != p.label
    ]
    if wrong:
        print(f"  {len(wrong)} mislabelled:")
        for start, actual, got in wrong:
            kind = "MISSED FAULT" if actual == ABNORMAL else "false alarm"
            print(f"    {start}  actual={actual:20s} predicted={got:20s} <- {kind}")
    else:
        print("  no label errors")
    print()


run("FIT split (in-sample, for reference only)", fit_frame, fit_truth)
run("HOLDOUT split (never seen during fitting or model selection)",
    hold_frame, hold_truth)

# Whole-stream figure, for completeness.
all_cycles = find_cycles(train_stream)
all_table = build_table(train_stream, all_cycles)
all_result = score_segments(
    truth, to_segments(all_table, classifier.predict(all_table))
)
print(f"--- Full Train.csv stream ---\n  {all_result.summary()}")
