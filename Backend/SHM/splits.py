"""Deterministic file splits. Confirmed groups always take precedence."""
import numpy as np
from sklearn.model_selection import KFold, StratifiedKFold

from data import require


def target_strata(y):
    # Equal targets stay in the same bin; do not fabricate target ranks with IDs.
    edges = np.unique(np.quantile(y, [.25, .5, .75]))
    return np.searchsorted(edges, np.asarray(y), side="right")


def make_splits(y, folds=5, seed=11, balanced=True, groups=None):
    y = np.asarray(y)
    n = len(y)
    if groups is not None and len(np.unique(groups)) < n:
        groups = np.asarray(groups)
        unique, inverse, counts = np.unique(groups, return_inverse=True, return_counts=True)
        require(len(unique) >= 2, "At least two independent groups are required for held-out validation")
        k = min(folds, len(unique))
        rng = np.random.default_rng(seed)
        order = np.arange(len(unique))
        rng.shuffle(order)
        order = order[np.argsort(-counts[order], kind="stable")]
        assignments, sizes = np.zeros(len(unique), dtype=int), np.zeros(k, dtype=int)
        for group in order:
            choices = np.flatnonzero(sizes == sizes.min())
            fold = int(rng.choice(choices))
            assignments[group] = fold
            sizes[fold] += counts[group]
        membership = assignments[inverse]
        result = [(np.flatnonzero(membership != f), np.flatnonzero(membership == f)) for f in range(k)]
    else:
        k = min(folds, n)
        require(k >= 2, "At least two files required for validation")
        bins = target_strata(y)
        counts = np.unique(bins, return_counts=True)[1]
        if balanced and counts.min() >= k:
            result = list(StratifiedKFold(k, shuffle=True, random_state=seed).split(np.zeros(n), bins))
        else:
            result = list(KFold(k, shuffle=True, random_state=seed).split(np.zeros(n)))
    require(sorted(np.concatenate([v for _, v in result]).tolist()) == list(range(n)), "Incomplete fold coverage")
    for train, val in result:
        require(not set(train) & set(val), "File overlap across split")
        if groups is not None:
            require(not set(np.asarray(groups)[train]) & set(np.asarray(groups)[val]), "Group overlap across split")
    return result
