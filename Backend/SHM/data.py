"""Strict file-level input audit and deterministic, label-free fatigue features."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import rainflow
from scipy.special import logsumexp

OBSERVATIONS = 581120
EXPONENTS = tuple(float(v) for v in np.arange(1, 12.01, .25))
CACHE_VERSION = f"raw-amplitude-v1-rainflow-{rainflow.__version__}"


def require(condition, message):
    """Checks stay active under python -O (unlike plain assertions)."""
    if not condition:
        raise ValueError(message)


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False), encoding="utf-8")


def validate_inventory(root):
    root = Path(root)
    train = sorted((root / "Train").glob("*.csv"))
    test = sorted((root / "Test").glob("*.csv"))
    labels = pd.read_csv(root / "Train_Labels.csv")
    require(list(labels.columns) == ["filename", "damage"], "Expected filename,damage label columns")
    require(len(train) == 64 and len(test) == 16 and len(labels) == 64,
            "Expected exactly 64 training files, 64 labels and 16 test files")
    require(labels.filename.notna().all() and labels.filename.is_unique, "Missing/duplicate label filename")
    require({p.name for p in train} == set(labels.filename), "Training filenames and labels differ")
    require({p.name for p in train} == {f"train{i:02d}.csv" for i in range(1, 65)}, "Unexpected training files")
    require({p.name for p in test} == {f"test{i:02d}.csv" for i in range(1, 17)}, "Unexpected test files")
    labels["damage"] = pd.to_numeric(labels.damage, errors="raise")
    require(np.isfinite(labels.damage).all() and (labels.damage > 0).all(), "Damage must be finite and positive")
    return train, test, labels.set_index("filename").damage


def read_signal(raw, expected_rows=OBSERVATIONS):
    frame = pd.read_csv(io.BytesIO(raw), header=None, dtype="float64", skip_blank_lines=False)
    require(frame.shape == (expected_rows, 1), f"Expected ({expected_rows}, 1), got {frame.shape}")
    x = frame.iloc[:, 0].to_numpy()
    require(np.isfinite(x).all(), "Signal contains missing/nonfinite observations")
    return x


def weighted_quantile(x, weights, quantile):
    order = np.argsort(x, kind="stable")
    x, weights = np.asarray(x)[order], np.asarray(weights)[order]
    i = np.searchsorted(np.cumsum(weights), quantile * weights.sum(), side="left")
    return float(x[min(int(i), len(x) - 1)])


def logq_column(m):
    return f"log_q_{m:g}"


def mean_column(m):
    return f"damage_mean_{m:g}"


def fingerprints(x):
    """Content-based anchors detect shifted exact overlaps, not only aligned blocks.

    A sample-value hash chooses about 1/1024 positions. A 512-sample SHA256
    verifies each anchor. This is a sparse screening check, not proof of independence.
    """
    bits = np.asarray(x, dtype="<f8").view(np.uint64).copy()
    bits ^= bits >> np.uint64(30)
    bits *= np.uint64(0xbf58476d1ce4e5b9)
    bits ^= bits >> np.uint64(27)
    bits *= np.uint64(0x94d049bb133111eb)
    bits ^= bits >> np.uint64(31)
    anchors = np.flatnonzero((bits & np.uint64(1023)) == 0)
    result = []
    for start in anchors:
        segment = x[start:start + 512]
        if len(segment) == 512 and np.ptp(segment) > 0:
            result.append([hashlib.sha256(segment.astype("<f8").tobytes()).hexdigest(), int(start)])
    return result


def extract_signal(x):
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
    for m in EXPONENTS:
        terms = logn + m * loga
        logq = float(logsumexp(terms))
        features[logq_column(m)] = logq
        features[mean_column(m)] = float(np.sum(np.exp(terms-logq)*means[positive]))
    return features


def extract_file(path, cache_dir, expected_rows=OBSERVATIONS):
    path, cache_dir = Path(path), Path(cache_dir)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    key = hashlib.sha256(f"{CACHE_VERSION}:{expected_rows}:{digest}".encode()).hexdigest()
    cache = cache_dir / f"{key}.json"
    if cache.exists():
        result = json.loads(cache.read_text(encoding="utf-8"))
    else:
        x = read_signal(raw, expected_rows)
        result = dict(sha256=digest, cache_version=CACHE_VERSION, features=extract_signal(x),
                      fingerprints=fingerprints(x))
        write_json(cache, result)
    return result


def check_nearest_waveforms(frame, paths, output):
    """Coarse lag checks on the six closest summary pairs; diagnostic only."""
    neighbors = pd.read_csv(Path(output) / "nearest_neighbors.csv").sort_values("standardized_distance")
    pairs, checked, loaded = [], set(), {}
    for row in neighbors.itertuples(index=False):
        pair = tuple(sorted([row.file_id, row.nearest_file]))
        if pair in checked:
            continue
        checked.add(pair)
        for name in pair:
            if name not in loaded:
                loaded[name] = read_signal(paths[name].read_bytes())
        x, y = (loaded[name] for name in pair)
        correlations = []
        for lag in [-4096, -1024, -256, 0, 256, 1024, 4096]:
            a, b = (x[lag:], y[:len(y)-lag]) if lag >= 0 else (x[:len(x)+lag], y[-lag:])
            # Coarse sampling keeps the audit cheap; not a complete lag search.
            a, b = a[::64], b[::64]
            rho = float(np.corrcoef(a, b)[0, 1]) if a.std()>0 and b.std()>0 else 0.
            correlations.append((lag, rho))
        best_lag, best_rho = max(correlations, key=lambda item: abs(item[1]))
        pairs.append(dict(file_a=pair[0], file_b=pair[1], summary_distance=row.standardized_distance,
                          zero_lag_correlation=dict(correlations)[0], best_checked_lag=best_lag,
                          best_checked_correlation=best_rho, creates_group=False))
        if len(pairs) == 6:
            break
    pd.DataFrame(pairs).to_csv(Path(output) / "waveform_similarity_checks.csv", index=False)


def waveform_relationship(a, b):
    """Conservative dependence screen, not an acquisition-session classifier.

    Require absolute full-signal correlation >= .99 and consistent correlation
    >= .95 in each of eight contiguous blocks. No labels enter this decision.
    """
    def correlation(x, y):
        return float(np.corrcoef(x, y)[0, 1]) if x.std()>0 and y.std()>0 else 0.
    rho = correlation(a, b)
    sign = 1 if rho >= 0 else -1
    block_min = min(sign*correlation(x, y) for x, y in zip(np.array_split(a, 8), np.array_split(b, 8)))
    return dict(full_correlation=rho, minimum_block_correlation=block_min,
                difference_correlation=correlation(np.diff(a), np.diff(b)),
                creates_group=bool(abs(rho)>=.99 and block_min>=.95))


def screen_correlated_waveforms(paths, output):
    """Screen all pairs cheaply, then verify candidate pairs at full resolution."""
    samples = np.stack([read_signal(path.read_bytes())[::64].copy() for path in paths])
    correlations = np.corrcoef(samples)
    loaded, relationships = {}, []
    for i, a in enumerate(paths):
        for j in range(i+1, len(paths)):
            # The .985 prescreen allows some sample/full correlation discrepancy.
            if abs(correlations[i, j]) < .985:
                continue
            b = paths[j]
            for path in [a, b]:
                if path.name not in loaded:
                    loaded[path.name] = read_signal(path.read_bytes())
            relationships.append(dict(file_a=a.name, file_b=b.name,
                sampled_correlation=float(correlations[i,j]),
                **waveform_relationship(loaded[a.name], loaded[b.name])))
    columns = ["file_a", "file_b", "sampled_correlation", "full_correlation",
               "minimum_block_correlation", "difference_correlation", "creates_group"]
    table = pd.DataFrame(relationships, columns=columns)
    table.to_csv(Path(output)/"correlated_waveforms.csv", index=False)
    return table


def audit_dataset(root, cache_dir, output_dir, group_path=None):
    train, test, labels = validate_inventory(root)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows, overlap_rows, seen, whole = [], [], {}, {}
    parent = {p.name: p.name for p in train + test}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        parent[find(a)] = find(b)

    for i, path in enumerate(train + test):
        record = extract_file(path, cache_dir)
        split = "train" if path in train else "test"
        rows.append(dict(file_id=path.name, split=split, sha256=record["sha256"], **record["features"]))
        if record["sha256"] in whole:
            other = whole[record["sha256"]]
            union(other, path.name)
            overlap_rows.append(dict(file_a=other, file_b=path.name, start_a=0, start_b=0, kind="whole_file"))
        whole[record["sha256"]] = path.name
        for digest, offset in record["fingerprints"]:
            if digest in seen and seen[digest][0] != path.name:
                other, other_offset = seen[digest]
                union(other, path.name)
                overlap_rows.append(dict(file_a=other, file_b=path.name, start_a=other_offset,
                                         start_b=offset, kind="exact_512_sample_overlap"))
            else:
                seen.setdefault(digest, (path.name, offset))
        print(f"Audit {i+1}/80: {path.name} ({record['features']['cycle_records']} cycle records)", flush=True)
    waveform_pairs = screen_correlated_waveforms(train+test, out)
    for pair in waveform_pairs.itertuples(index=False):
        if pair.creates_group:
            union(pair.file_a, pair.file_b)
    if group_path:
        groups = pd.read_csv(group_path, dtype=str)
        require(set(groups.columns) == {"filename", "group"}, "Group CSV must have filename,group columns")
        require(groups.filename.is_unique and groups.group.notna().all(), "Missing/duplicate group data")
        require(set(groups.filename) == {p.name for p in train}, "Groups must cover exactly the 64 training files")
        for _, members in groups.groupby("group"):
            names = members.filename.tolist()
            for name in names[1:]:
                union(names[0], name)
    frame = pd.DataFrame(rows).set_index("file_id", drop=False)
    frame["group"] = [find(name) for name in frame.index]
    frame["damage"] = frame.file_id.map(labels)
    frame.to_csv(out / "features.csv", index=False)
    pd.DataFrame(overlap_rows, columns=["file_a", "file_b", "start_a", "start_b", "kind"]).to_csv(out / "overlaps.csv", index=False)
    columns = ["mean", "sd", "rms", "range_max", "a95", "cycle_count"]
    z = frame[columns].to_numpy()
    scale = z.std(axis=0)
    z = (z-z.mean(axis=0))/np.where(scale > 0, scale, 1)
    distance = np.sqrt(((z[:, None]-z[None, :])**2).sum(axis=2))
    np.fill_diagonal(distance, np.inf)
    neighbors = distance.argmin(axis=1)
    pd.DataFrame(dict(file_id=frame.file_id.to_numpy(), nearest_file=frame.file_id.to_numpy()[neighbors],
                      standardized_distance=distance[np.arange(len(frame)), neighbors])).to_csv(out / "nearest_neighbors.csv", index=False)
    check_nearest_waveforms(frame, {p.name: p for p in train+test}, out)
    summary = dict(training_files=64, test_files=16, observations_per_file=OBSERVATIONS,
                   total_observations=80*OBSERVATIONS, columns=1, header=False, finite_numeric=True,
                   exact_label_alignment=True, damage_min=float(labels.min()), damage_max=float(labels.max()),
                   duplicate_files=80-len(whole), overlap_matches=len(overlap_rows),
                   correlated_waveform_pairs=int(waveform_pairs.creates_group.sum()),
                   training_groups=int(frame.loc[frame.split == "train", "group"].nunique()),
                   rainflow_version=rainflow.__version__, range_to_amplitude_factor=.5,
                   raw_preprocessing="none", independence_established=False,
                   overlap_check="Sparse value-anchored exact 512-sample matches; no guarantee of independence",
                   nearest_neighbors="Diagnostic only; similarities are NOT inferred acquisition groups",
                   waveform_group_rule="Conservative dependence groups: abs(full correlation)>=0.99 and all eight sign-consistent block correlations>=0.95; candidates screened at abs(stride-64 correlation)>=0.985",
                   grouping_uses_labels=False, groups_are_verified_sessions=False,
                   units="unverified", sample_frequency="unverified")
    write_json(out / "audit.json", summary)
    return frame, summary
