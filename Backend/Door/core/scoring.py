"""Official Door metric: IoU-weighted F1.

Implements Door_Subsystem_Info_Kit.md Section 4 exactly, so that every
modelling decision can be measured on the metric we are actually ranked on
rather than on a proxy such as plain label accuracy.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

NORMAL = "Normal"
ABNORMAL = "Abnormal resistance"


def parse_time(value) -> dt.datetime:
    """Parse the dataset's native timestamp, falling back to ISO.

    Native format is Year-Month-Date-Hour-Minute-Second-Millisecond with no
    zero padding, e.g. ``2023-7-5-0-11-17-664``. The info kit states both this
    and any ISO-parseable timestamp are accepted in a submission, so the
    scorer accepts both too.
    """
    if isinstance(value, dt.datetime):
        return value
    text = str(value).strip()
    parts = text.split("-")
    if len(parts) == 7:
        year, month, day, hour, minute, second, milli = (int(p) for p in parts)
        return dt.datetime(year, month, day, hour, minute, second, milli * 1000)
    return dt.datetime.fromisoformat(text)


def format_time(moment: dt.datetime) -> str:
    """Render a timestamp back in the dataset's native format."""
    return "-".join(
        str(v)
        for v in (
            moment.year,
            moment.month,
            moment.day,
            moment.hour,
            moment.minute,
            moment.second,
            moment.microsecond // 1000,
        )
    )


@dataclass(frozen=True)
class Segment:
    """One door-open/close cycle: a time range plus its status label."""

    start: dt.datetime
    end: dt.datetime
    label: str

    @property
    def duration(self) -> float:
        return (self.end - self.start).total_seconds()


def iou(true_seg: Segment, pred_seg: Segment) -> float:
    """Intersection-over-union of two time ranges, per info kit Section 4.1."""
    intersection = min(true_seg.end, pred_seg.end) - max(true_seg.start, pred_seg.start)
    intersection = max(0.0, intersection.total_seconds())
    union = true_seg.duration + pred_seg.duration - intersection
    if union <= 0:
        return 0.0
    return intersection / union


@dataclass
class ScoreResult:
    """Full breakdown of a scoring run, not just the headline number."""

    score: float
    soft_recall: float
    soft_precision: float
    matches: list[tuple[int, int, float]]  # (true index, pred index, IoU)
    n_true: int
    n_pred: int

    @property
    def n_matched(self) -> int:
        return len(self.matches)

    @property
    def n_missed(self) -> int:
        return self.n_true - self.n_matched

    @property
    def n_false_positive(self) -> int:
        return self.n_pred - self.n_matched

    @property
    def mean_iou(self) -> float:
        if not self.matches:
            return 0.0
        return sum(m[2] for m in self.matches) / len(self.matches)

    def summary(self) -> str:
        return (
            f"score={self.score:.4f}  "
            f"soft_recall={self.soft_recall:.4f}  "
            f"soft_precision={self.soft_precision:.4f}  "
            f"matched={self.n_matched}/{self.n_true}  "
            f"missed={self.n_missed}  false_pos={self.n_false_positive}  "
            f"mean_IoU={self.mean_iou:.4f}"
        )


def score_segments(truth: list[Segment], predicted: list[Segment]) -> ScoreResult:
    """Score predictions against ground truth using IoU-weighted F1.

    Matching rules (info kit Section 4.1): a predicted segment may only match a
    true segment carrying the *same* label; the pair must have IoU > 0; and
    matching is one-to-one, assigned greedily from the highest IoU downward.
    """
    candidates = []
    for t_idx, true_seg in enumerate(truth):
        for p_idx, pred_seg in enumerate(predicted):
            if true_seg.label != pred_seg.label:
                continue  # wrong label cannot match at all
            overlap = iou(true_seg, pred_seg)
            if overlap > 0:
                candidates.append((overlap, t_idx, p_idx))

    # Greedy assignment, best-overlapping pairs first.
    candidates.sort(key=lambda c: c[0], reverse=True)
    used_true: set[int] = set()
    used_pred: set[int] = set()
    matches: list[tuple[int, int, float]] = []
    for overlap, t_idx, p_idx in candidates:
        if t_idx in used_true or p_idx in used_pred:
            continue
        used_true.add(t_idx)
        used_pred.add(p_idx)
        matches.append((t_idx, p_idx, overlap))

    total_iou = sum(m[2] for m in matches)
    soft_recall = total_iou / len(truth) if truth else 0.0
    soft_precision = total_iou / len(predicted) if predicted else 0.0
    denominator = soft_recall + soft_precision
    score = 0.0 if denominator == 0 else 2 * soft_recall * soft_precision / denominator

    return ScoreResult(
        score=score,
        soft_recall=soft_recall,
        soft_precision=soft_precision,
        matches=matches,
        n_true=len(truth),
        n_pred=len(predicted),
    )
