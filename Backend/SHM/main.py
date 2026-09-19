"""SHM CLI: audit, development CV, frozen nested validation, and inference."""
from __future__ import annotations

# Preserve direct-script CLI commands without exposing SHM's modules at top level.
if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "SHM"

import argparse
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .data import CACHE_VERSION, OBSERVATIONS, audit_dataset, extract_file, require, write_json

HERE = Path(__file__).resolve().parent


def default_protocol(include_hybrid=False, hybrid_reason=None):
    from .models import candidates
    require(not include_hybrid or bool(hybrid_reason), "Record the residual evidence with --hybrid-reason when enabling a hybrid")
    return dict(version=1, development_seeds=[11, 22, 33, 44, 55],
        outer_seeds=[101, 202, 303, 404, 505], sensitivity_seeds=[606, 707, 808],
        inner_seed=1701, refit_seeds=[211, 222, 233, 244, 255], tolerance=.01,
        outer_folds=5, inner_folds=4, residual_folds=4, target_bins=4,
        bootstrap_samples=5000, candidates=[asdict(c) for c in candidates(include_hybrid)],
        hybrid_evidence=hybrid_reason,
        selection="Within 0.01 absolute MAPE of minimum: lowest complexity, then MAPE, then name",
        complexity_order=["constant", "stress/physics", "flexible/two_moment", "small", "hybrid"],
        development_reuse="Internal evaluation; new seeds cannot erase adaptive development reuse")


def load_protocol(args):
    from .models import Candidate, candidates
    protocol = json.loads(args.protocol.read_text(encoding="utf-8")) if args.protocol else default_protocol(args.include_hybrid, args.hybrid_reason)
    reference = default_protocol()
    for key, count in [("development_seeds", 5), ("outer_seeds", 5), ("sensitivity_seeds", 3), ("refit_seeds", 5)]:
        require(len(protocol[key]) == count and len(set(protocol[key])) == count, f"Expected {count} distinct {key}")
    for key in ["version", "outer_folds", "inner_folds", "residual_folds", "target_bins", "bootstrap_samples", "tolerance"]:
        require(protocol[key] == reference[key], f"Unsupported protocol {key}; this implementation follows {reference[key]}")
    cs = [Candidate(**c) for c in protocol["candidates"]]
    allowed = {c.name: c for c in candidates(True)}
    require(cs and len({c.name for c in cs}) == len(cs), "Empty or duplicate candidates")
    require(all(allowed.get(c.name) == c for c in cs), "Protocol contains unsupported candidate settings")
    require({"median", "weighted_median"}.issubset({c.family for c in cs}), "Keep both constant baselines in the frozen selection set")
    require(not any(c.family == "hybrid" for c in cs) or bool(protocol.get("hybrid_evidence")), "Hybrid requires recorded residual evidence")
    return protocol, cs


def freeze_protocol(output, protocol, frame):
    payload = dict(protocol=protocol, feature_version=CACHE_VERSION,
                   training_data=frame.loc[frame.split == "train", ["file_id", "sha256", "damage", "group"]].to_dict("records"))
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    path = output / "frozen_protocol.json"
    if path.exists():
        require(json.loads(path.read_text(encoding="utf-8"))["sha256"] == digest,
                "Protocol/data changed: choose a new --output directory instead of overwriting the frozen run")
    write_json(path, dict(sha256=digest, **payload))
    return digest


def run_development(train, cs, protocol, output):
    from .validation import evaluate_candidates, save_reports, select_candidate
    print(f"Development: {len(cs)} candidates, 5 folds x 5 repeats", flush=True)
    oof, splits, fits = evaluate_candidates(train, cs, protocol["development_seeds"], context="development")
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(splits).to_csv(output / "splits.csv", index=False)
    write_json(output / "fits.json", fits)
    summary = save_reports(oof, output, train)
    selected, scores = select_candidate(oof, cs, protocol["tolerance"])
    write_json(output / "exploratory_selection.json", dict(candidate=asdict(selected), mape=scores[selected.name],
        interpretation="Selected on these validation results: development score is optimistic; not a final test estimate"))
    print(summary.head(8).to_string(index=False), flush=True)


def run_final(train, test, cs, protocol, output, protocol_hash):
    from .models import FittedModel, fit_model
    from .validation import (evaluate_candidates, nested_validation, save_parameter_summary,
                             save_reports, select_candidate)
    output.mkdir(parents=True, exist_ok=True)
    for label, seeds, balanced in [("balanced", protocol["outer_seeds"], True),
                                  ("unbalanced_sensitivity", protocol["sensitivity_seeds"], False)]:
        sub = output / label
        sub.mkdir(parents=True, exist_ok=True)
        oof, splits, selections, inner = nested_validation(train, cs, seeds, protocol["inner_seed"], balanced, protocol["tolerance"])
        pd.DataFrame(splits).to_csv(sub / "splits.csv", index=False)
        inner.to_csv(sub / "inner_scores.csv", index=False)
        write_json(sub / "selections.json", selections)
        summary = save_reports(oof, sub, train)
        save_parameter_summary(selections, sub)
        print(f"{label}: MAPE={summary.iloc[0].mape:.6f}, score={summary.iloc[0].score:.6f}", flush=True)
    # This selection is independent of the outer results: same frozen candidates
    # and selection rule, using all 64 files and the prespecified refit seeds.
    print("Selecting final refit on all 64 files", flush=True)
    oof, splits, _ = evaluate_candidates(train, cs, protocol["refit_seeds"], context="full_data_selection")
    selected, scores = select_candidate(oof, cs, protocol["tolerance"])
    pd.DataFrame(splits).to_csv(output / "refit_splits.csv", index=False)
    pd.DataFrame([dict(candidate=name, mape=score) for name, score in scores.items()]).to_csv(output / "refit_scores.csv", index=False)
    model = fit_model(selected, train, train.damage.to_numpy(), train.group.to_numpy(), seed=9701)
    artifact = dict(version=1, protocol_sha256=protocol_hash, feature_version=CACHE_VERSION,
        observations=OBSERVATIONS, model=model.to_dict(), training_files=train.file_id.tolist(),
        dependencies={name: importlib.metadata.version(name) for name in ["numpy", "pandas", "scipy", "scikit-learn", "rainflow"]},
        refit_selection_mape=scores[selected.name], refit_selection_is_test_estimate=False)
    write_json(output / "model.json", artifact)
    # Exercise the portable serialization before producing the deliverable.
    restored = FittedModel.from_dict(json.loads((output / "model.json").read_text(encoding="utf-8"))["model"])
    predictions = restored.predict(test)
    pd.DataFrame(dict(file_id=test.file_id.to_numpy(), prediction=predictions)).to_csv(output / "shm_predictions.csv", index=False)
    # Train/test support diagnostics are descriptive and do not change selection.
    cols = ["sd", "mean", "rms", "amplitude_max", "a95", "cycle_count"]
    shift = []
    for column in cols:
        low, high = train[column].min(), train[column].max()
        for _, row in test.iterrows():
            if row[column] < low or row[column] > high:
                shift.append(dict(file_id=row.file_id, feature=column, value=row[column], training_min=low, training_max=high))
    pd.DataFrame(shift, columns=["file_id", "feature", "value", "training_min", "training_max"]).to_csv(output / "test_support_flags.csv", index=False)
    print(f"Final model: {selected.name}; predictions: {output / 'shm_predictions.csv'}", flush=True)


def predict(args):
    from .core.data import read_raw
    from .core.model import MODEL_PATH, ShmModel
    from .prediction.predict import predict_file

    require(args.input is not None, "predict requires --input")
    model = ShmModel.load(args.model or MODEL_PATH)
    files = sorted(args.input.glob("*.csv"))
    require(len(files) > 0, "No input CSV files")
    records = [{"file_id": p.name, **predict_file(read_raw(p), model)} for p in files]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records)[['file_id', 'prediction']].to_csv(args.output, index=False)
    print(f"Saved {len(files)} predictions to {args.output}", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["audit", "develop", "final", "all", "predict"], nargs="?", default="all")
    parser.add_argument("--data", type=Path, default=HERE / "dataset_shm" / "SHM")
    parser.add_argument("--output", type=Path, help="Report directory, or prediction CSV for predict")
    parser.add_argument("--cache", type=Path, default=HERE / ".cache")
    parser.add_argument("--groups", type=Path, help="Optional verified filename,group CSV for all 64 training files")
    parser.add_argument("--protocol", type=Path, help="Frozen protocol JSON; defaults are saved before evaluation")
    parser.add_argument("--include-hybrid", action="store_true")
    parser.add_argument("--hybrid-reason", help="Evidence for enabling residual correction; recorded in protocol")
    parser.add_argument("--model", type=Path)
    parser.add_argument("--input", type=Path, help="Inference-only directory containing stress CSVs")
    args = parser.parse_args(argv)
    if args.output is None:
        args.output = HERE / "shm_predictions.csv" if args.command == "predict" else HERE / "outputs" / "grouped"
    if args.command == "predict":
        predict(args)
        return
    protocol, cs = load_protocol(args)
    frame, audit = audit_dataset(args.data, args.cache, args.output / "audit", args.groups)
    if args.command == "audit":
        print(json.dumps(audit, indent=2))
        return
    protocol_hash = freeze_protocol(args.output, protocol, frame)
    write_json(args.output / "protocol.json", protocol)
    train, test = frame[frame.split == "train"], frame[frame.split == "test"]
    if args.command in {"develop", "all"}:
        run_development(train, cs, protocol, args.output / "development")
    if args.command in {"final", "all"}:
        run_final(train, test, cs, protocol, args.output / "final", protocol_hash)


if __name__ == "__main__":
    main()
