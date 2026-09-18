"""Unit tests for scoring.py.

Checks the metric reproduces every behaviour the info kit spells out.

Section 4.2 describes five scenarios in words; each is asserted here so we know
the metric we optimise against is the metric we are graded on.
"""

from __future__ import annotations

import datetime as dt

from core.scoring import (
    ABNORMAL,
    NORMAL,
    Segment,
    format_time,
    iou,
    parse_time,
    score_segments,
)

BASE = dt.datetime(2023, 7, 5)


def seg(start_s: float, end_s: float, label: str = NORMAL) -> Segment:
    return Segment(
        BASE + dt.timedelta(seconds=start_s),
        BASE + dt.timedelta(seconds=end_s),
        label,
    )


def check(name: str, got, want, tol: float = 1e-9) -> None:
    ok = abs(got - want) < tol if isinstance(want, float) else got == want
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: got {got!r}, want {want!r}")
    assert ok, name


print("Timestamp parsing")
check("native format", parse_time("2023-7-5-0-11-17-664"),
      dt.datetime(2023, 7, 5, 0, 11, 17, 664000))
check("round trip", format_time(parse_time("2023-7-5-0-11-17-664")),
      "2023-7-5-0-11-17-664")
check("ISO fallback", parse_time("2023-07-05T00:11:17.664"),
      dt.datetime(2023, 7, 5, 0, 11, 17, 664000))

print("\nIoU mechanics (Section 4.1)")
check("identical ranges -> 1.0", iou(seg(0, 10), seg(0, 10)), 1.0)
check("no overlap -> 0.0", iou(seg(0, 10), seg(20, 30)), 0.0)
check("touching ranges -> 0.0", iou(seg(0, 10), seg(10, 20)), 0.0)
# 5s overlap, union = 10 + 10 - 5 = 15
check("half overlap -> 1/3", iou(seg(0, 10), seg(5, 15)), 1 / 3)

print("\nSection 4.2 scenario: perfect submission")
truth = [seg(0, 10), seg(20, 30, ABNORMAL), seg(40, 50)]
result = score_segments(truth, list(truth))
check("score", result.score, 1.0)
check("soft_recall", result.soft_recall, 1.0)
check("soft_precision", result.soft_precision, 1.0)

print("\nSection 4.2 scenario: wrong label cannot match")
# Perfectly overlapping timing but the opposite label.
result = score_segments([seg(0, 10, NORMAL)], [seg(0, 10, ABNORMAL)])
check("score", result.score, 0.0)
check("no matches", result.n_matched, 0)
check("counts as a miss", result.n_missed, 1)
check("and as a false positive", result.n_false_positive, 1)

print("\nSection 4.2 scenario: missing segments lower recall")
truth = [seg(0, 10), seg(20, 30), seg(40, 50)]
result = score_segments(truth, [seg(0, 10)])  # found 1 of 3, perfectly
check("soft_recall", result.soft_recall, 1 / 3)
check("soft_precision", result.soft_precision, 1.0)
check("score", result.score, 2 * (1 / 3) * 1.0 / (1 / 3 + 1.0))

print("\nSection 4.2 scenario: spurious extras lower precision")
truth = [seg(0, 10)]
result = score_segments(truth, [seg(0, 10), seg(100, 110), seg(200, 210)])
check("soft_recall", result.soft_recall, 1.0)
check("soft_precision", result.soft_precision, 1 / 3)
check("over-segmenting is penalised", result.score < 1.0, True)

print("\nSection 4.2 scenario: sloppy boundaries reduce credit")
truth = [seg(0, 10)]
tight = score_segments(truth, [seg(0, 10)])
loose = score_segments(truth, [seg(5, 15)])
check("loose still matches", loose.n_matched, 1)
check("but earns less than tight", loose.score < tight.score, True)
check("credit is the IoU itself", loose.matches[0][2], 1 / 3)

print("\nOne-to-one greedy matching (Section 4.1 rule 3)")
# Two predictions overlap one true segment; only the better one may match.
truth = [seg(0, 10)]
result = score_segments(truth, [seg(0, 9), seg(1, 10)])
check("only one match allowed", result.n_matched, 1)
check("the higher-IoU pair wins", result.matches[0][2], 9 / 10)
check("the loser is a false positive", result.n_false_positive, 1)

print("\nEdge cases")
check("no predictions -> 0", score_segments([seg(0, 10)], []).score, 0.0)
check("no truth -> 0", score_segments([], [seg(0, 10)]).score, 0.0)
check("both empty -> 0", score_segments([], []).score, 0.0)

print("\nAll scorer tests passed.")
