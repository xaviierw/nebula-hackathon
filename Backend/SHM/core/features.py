"""Deterministic raw rainflow mechanics shared by inference and offline training."""
import numpy as np
import rainflow
from scipy.special import logsumexp
from .errors import ShmInputError

EXPONENTS = tuple(float(v) for v in np.arange(1, 12.01, .25))
CACHE_VERSION = f"raw-amplitude-v1-rainflow-{rainflow.__version__}"


def require(condition, message):
    if not condition:
        raise ShmInputError(message)


def weighted_quantile(x, weights, quantile):
    order = np.argsort(x, kind="stable")
    x, weights = np.asarray(x)[order], np.asarray(weights)[order]
    i = np.searchsorted(np.cumsum(weights), quantile * weights.sum(), side="left")
    return float(x[min(int(i), len(x) - 1)])


def logq_column(m):
    return f"log_q_{m:g}"


def mean_column(m):
    return f"damage_mean_{m:g}"


def extract_signal(x, exponents=EXPONENTS):
    cycles = np.asarray(list(rainflow.extract_cycles(x)), dtype=np.float64)
    require(cycles.ndim == 2 and len(cycles) > 0, "No rainflow cycles; cannot construct positive fatigue moments")
    ranges, means, counts = cycles[:, 0], cycles[:, 1], cycles[:, 2]
    require(np.isin(counts, [.5, 1.]).all(), "Unexpected rainflow count convention")
    start, end = cycles[:, 3].astype(int), cycles[:, 4].astype(int)
    require(np.allclose(ranges, np.abs(x[start] - x[end]), rtol=1e-12, atol=1e-12), "Range convention check failed")
    require(np.allclose(means, (x[start] + x[end]) / 2, rtol=1e-12, atol=1e-12), "Cycle mean check failed")
    amplitudes = ranges / 2
    a50 = weighted_quantile(amplitudes, counts, .5)
    a95 = weighted_quantile(amplitudes, counts, .95)
    require(a50 > 0 and a95 > 0 and np.std(x) > 0, "Degenerate signal/amplitude quantile")
    features = dict(n=len(x), mean=float(x.mean()), sd=float(x.std()), rms=float(np.sqrt(np.mean(x*x))),
                    minimum=float(x.min()), maximum=float(x.max()), cycle_records=len(cycles),
                    full_records=int(np.sum(counts == 1)), half_records=int(np.sum(counts == .5)),
                    cycle_count=float(counts.sum()), range_min=float(ranges.min()),
                    range_median=float(np.median(ranges)), range_max=float(ranges.max()),
                    amplitude_min=float(amplitudes.min()), amplitude_median=float(np.median(amplitudes)),
                    amplitude_max=float(amplitudes.max()), a50=a50, a95=a95,
                    breadth=float(np.log(a95/a50)), tail=float(np.log(amplitudes.max()/a95)))
    positive = amplitudes > 0
    loga, logn = np.log(amplitudes[positive]), np.log(counts[positive])
    for m in exponents:
        terms = logn + m * loga
        logq = float(logsumexp(terms))
        features[logq_column(m)] = logq
        features[mean_column(m)] = float(np.sum(np.exp(terms-logq)*means[positive]))
    return features
