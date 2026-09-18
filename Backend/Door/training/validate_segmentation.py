"""Validate the gap-based segmenter against Train_Segments_Answer.csv.

Checks (a) the right number of cycles, (b) exact boundary timestamps, (c) exact
row counts, (d) robustness of the gap threshold, and (e) that the chronological
split keeps every cycle intact.
"""

from __future__ import annotations

from core.data import (
    DATA_DIR,
    GAP_SECONDS,
    TIME,
    chronological_split,
    cycle_bounds,
    find_cycles,
    load_stream,
    load_truth,
    load_truth_frame,
)
from core.scoring import Segment, score_segments

train = load_stream(DATA_DIR / "Train.csv")
truth = load_truth(DATA_DIR / "Train_Segments_Answer.csv")
truth_frame = load_truth_frame(DATA_DIR / "Train_Segments_Answer.csv")

print(f"Train.csv: {len(train)} rows, {len(truth)} labelled cycles")

# --- (a)-(c) exact recovery of the ground-truth boundaries ------------------
cycles = find_cycles(train)
print(f"\nSegmenter found {len(cycles)} cycles (truth has {len(truth)})")
assert len(cycles) == len(truth), "cycle count mismatch"

exact_start = exact_end = exact_rows = 0
for cycle, true_seg, n_rows in zip(cycles, truth, truth_frame["n_rows"]):
    start, end = cycle_bounds(train, cycle)
    exact_start += start == true_seg.start
    exact_end += end == true_seg.end
    exact_rows += (cycle[1] - cycle[0] + 1) == n_rows

print(f"  exact start timestamps: {exact_start}/{len(truth)}")
print(f"  exact end timestamps:   {exact_end}/{len(truth)}")
print(f"  exact row counts:       {exact_rows}/{len(truth)}")

# Score the segmentation alone by handing it the true labels, isolating
# boundary quality from classification quality.
perfect_labels = [
    Segment(*cycle_bounds(train, c), t.label) for c, t in zip(cycles, truth)
]
result = score_segments(truth, perfect_labels)
print(f"\nSegmentation ceiling (true labels assumed): {result.summary()}")

# --- (d) the gap threshold is structural, not tuned --------------------------
print("\nGap-threshold sensitivity:")
for gap in (0.05, 0.1, 0.5, 1.0, 5.0, 10.0):
    n = len(find_cycles(train, gap_seconds=gap))
    print(f"  gap > {gap:>5}s -> {n} cycles {'OK' if n == len(truth) else 'MISMATCH'}")

times = train[TIME]
deltas = [(times[i] - times[i - 1]).total_seconds() for i in range(1, len(times))]
intra = [d for d in deltas if d <= GAP_SECONDS]
inter = [d for d in deltas if d > GAP_SECONDS]
print(f"\n  within-cycle sampling: min={min(intra):.3f}s max={max(intra):.3f}s")
print(f"  between-cycle idle gap: min={min(inter):.3f}s max={max(inter):.3f}s")
print(f"  separation ratio: {min(inter) / max(intra):.0f}x")

# --- (e) the chronological split cuts only in idle gaps ---------------------
fit_frame, fit_truth, hold_frame, hold_truth = chronological_split(train, truth)
print(
    f"\nChronological 70/30 split:"
    f"\n  fit:     {len(fit_frame):5} rows, {len(fit_truth)} cycles"
    f"\n  holdout: {len(hold_frame):5} rows, {len(hold_truth)} cycles"
)
assert len(fit_truth) + len(hold_truth) == len(truth), "cycles lost in the split"
assert len(fit_frame) + len(hold_frame) == len(train), "rows lost in the split"

# Every cycle must be wholly on one side of the cut.
for name, frame, side_truth in (("fit", fit_frame, fit_truth), ("holdout", hold_frame, hold_truth)):
    side_cycles = find_cycles(frame)
    assert len(side_cycles) == len(side_truth), f"{name}: cycle count changed after split"
    for cycle, true_seg in zip(side_cycles, side_truth):
        start, end = cycle_bounds(frame, cycle)
        assert start == true_seg.start and end == true_seg.end, f"{name}: cycle cut in half"
    print(f"  {name}: all {len(side_cycles)} cycles intact, boundaries exact")

fit_labels = [t.label for t in fit_truth]
hold_labels = [t.label for t in hold_truth]
for name, labels in (("fit", fit_labels), ("holdout", hold_labels)):
    abnormal = sum(1 for lab in labels if lab != "Normal")
    print(f"  {name} class balance: {len(labels) - abnormal} Normal / {abnormal} Abnormal")

print("\nSegmentation validated.")
