"""Repeated development CV and nested evaluation of the full selection rule."""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from data import require, write_json
from models import fit_model
from splits import make_splits, target_strata


def evaluate_candidates(frame, candidates, seeds, folds=5, balanced=True, context="cv"):
    y = frame.damage.to_numpy()
    groups = frame.group.to_numpy()
    rows, splits, fits = [], [], []
    for repeat, seed in enumerate(seeds):
        for fold, (train, val) in enumerate(make_splits(y, folds, seed, balanced, groups)):
            splits.extend(dict(context=context, repeat=repeat, seed=seed, fold=fold,
                               file_id=frame.iloc[i].file_id, role="validation") for i in val)
            for candidate in candidates:
                model = fit_model(candidate, frame.iloc[train], y[train], groups[train], seed=seed+fold+1000)
                prediction = model.predict(frame.iloc[val])
                fits.append(dict(repeat=repeat, fold=fold, candidate_name=candidate.name, **model.to_dict()))
                rows.extend(dict(candidate=candidate.name, family=candidate.family, repeat=repeat,
                                 seed=seed, fold=fold, file_id=frame.iloc[i].file_id,
                                 group=groups[i], target=float(y[i]), prediction=float(pred),
                                 ape=float(abs(y[i]-pred)/y[i])) for i, pred in zip(val, prediction))
    return pd.DataFrame(rows), splits, fits


def select_candidate(oof, candidates, tolerance=.01):
    scores = oof.groupby("candidate").ape.mean().to_dict()
    eligible = [c for c in candidates if scores[c.name] <= min(scores.values()) + tolerance]
    # First minimise complexity, then error. Names only break exact ties.
    return min(eligible, key=lambda c: (c.complexity, scores[c.name], c.name)), scores


def nested_validation(frame, candidates, outer_seeds, inner_seed, balanced=True, tolerance=.01):
    y, groups = frame.damage.to_numpy(), frame.group.to_numpy()
    outer_rows, split_rows, selections, inner_tables = [], [], [], []
    for repeat, seed in enumerate(outer_seeds):
        for fold, (train, val) in enumerate(make_splits(y, 5, seed, balanced, groups)):
            print(f"Nested {'balanced' if balanced else 'unbalanced'} repeat {repeat+1}/{len(outer_seeds)}, fold {fold+1}", flush=True)
            training = frame.iloc[train]
            inner, inner_splits, _ = evaluate_candidates(training, candidates,
                [inner_seed+repeat*100+fold], folds=4, balanced=True, context=f"inner_{repeat}_{fold}")
            candidate, scores = select_candidate(inner, candidates, tolerance)
            for item in inner_splits:
                item.update(outer_repeat=repeat, outer_fold=fold)
            split_rows.extend(inner_splits)
            inner_tables.extend(dict(outer_repeat=repeat, outer_fold=fold, candidate=name, mape=score)
                                for name, score in scores.items())
            model = fit_model(candidate, training, y[train], groups[train], seed=seed+fold+1000)
            prediction = model.predict(frame.iloc[val])
            selections.append(dict(repeat=repeat, fold=fold, candidate_name=candidate.name,
                                   inner_mape=scores[candidate.name], training_files=len(train), **model.to_dict()))
            for i, pred in zip(val, prediction):
                outer_rows.append(dict(candidate="selection_procedure", family=candidate.family,
                    selected_candidate=candidate.name, repeat=repeat, seed=seed, fold=fold,
                    file_id=frame.iloc[i].file_id, group=groups[i], target=float(y[i]),
                    prediction=float(pred), ape=float(abs(y[i]-pred)/y[i])))
                split_rows.append(dict(context="outer", repeat=repeat, seed=seed, fold=fold,
                                       file_id=frame.iloc[i].file_id, role="validation"))
    return pd.DataFrame(outer_rows), split_rows, selections, pd.DataFrame(inner_tables)


def bootstrap_file_errors(per_file, seed=901, samples=5000):
    """Conditional resampling: repeat vectors stay together; groups stay together."""
    rng = np.random.default_rng(seed)
    units = [group.ape.to_numpy() for _, group in per_file.groupby("group")]
    totals = np.array([v.sum() for v in units])
    sizes = np.array([len(v) for v in units])
    picks = rng.integers(0, len(units), size=(samples, len(units)))
    simulated = totals[picks].sum(axis=1)/sizes[picks].sum(axis=1)
    return np.quantile(simulated, [.025, .975]).tolist()


def summarise(oof, bootstrap=True):
    summaries, per_files, repeats, folds = [], [], [], []
    for name, part in oof.groupby("candidate", sort=False):
        require(not part.duplicated(["repeat", "file_id"]).any(), "Duplicate OOF appearance")
        coverage = part.groupby("file_id").repeat.nunique()
        require(coverage.nunique() == 1 and coverage.iloc[0] == part.repeat.nunique(), "Unequal repeated OOF coverage")
        counts = part.groupby("file_id").target.nunique()
        require((counts == 1).all(), "Targets changed across repeats")
        per = part.groupby("file_id", as_index=False).agg(target=("target", "first"), group=("group", "first"),
                    prediction=("prediction", "mean"), prediction_sd=("prediction", "std"), ape=("ape", "mean"),
                    worst_appearance_ape=("ape", "max"))
        per["candidate"] = name
        per["quartile"] = target_strata(per.target)+1
        per["log_residual"] = np.log(per.target)-np.log(per.prediction)
        per["prediction_sd"] = per.prediction_sd.fillna(0)
        rep = part.groupby("repeat", as_index=False).ape.mean().rename(columns={"ape": "mape"})
        rep["candidate"] = name
        fold = part.groupby(["repeat", "fold"], as_index=False).agg(mape=("ape", "mean"), n=("ape", "size"))
        fold["candidate"] = name
        mape = float(part.ape.mean())
        summary = dict(candidate=name, mape=mape, score=max(0., 1-mape),
            repeat_sd=float(rep.mape.std(ddof=1)) if len(rep)>1 else 0.,
            repeat_min=float(rep.mape.min()), repeat_max=float(rep.mape.max()),
            file_median_ape=float(per.ape.median()), file_p90_ape=float(per.ape.quantile(.9)),
            max_file_mean_ape=float(per.ape.max()), max_appearance_ape=float(part.ape.max()),
            top5_error_share=float(per.ape.nlargest(5).sum()/per.ape.sum()) if per.ape.sum()>0 else 0.,
            prediction_average_mape=float(np.mean(abs(per.target-per.prediction)/per.target)),
            files=len(per), resampling_units=int(per.group.nunique()), held_out_appearances=len(part))
        if bootstrap:
            low, high = bootstrap_file_errors(per)
            summary.update(conditional_bootstrap_low=low, conditional_bootstrap_high=high)
        summaries.append(summary)
        per_files.append(per); repeats.append(rep); folds.append(fold)
    return pd.DataFrame(summaries).sort_values("mape"), pd.concat(per_files), pd.concat(repeats), pd.concat(folds)


def save_reports(oof, output, frame, bootstrap=True):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    summary, per, repeats, folds = summarise(oof, bootstrap)
    oof = oof.copy()
    oof["log_residual"] = np.log(oof.target)-np.log(oof.prediction)
    oof.to_csv(output / "oof_predictions.csv", index=False)
    summary.to_csv(output / "summary.csv", index=False)
    per.to_csv(output / "per_file.csv", index=False)
    repeats.to_csv(output / "repeats.csv", index=False)
    folds.to_csv(output / "folds.csv", index=False)
    per.groupby(["candidate", "quartile"]).agg(mape=("ape", "mean"), files=("ape", "size")).to_csv(output / "target_quartiles.csv")
    per.sort_values("ape", ascending=False).groupby("candidate").head(5).to_csv(output / "worst_files.csv", index=False)
    features = ["rms", "mean", "sd", "amplitude_max", "cycle_count", "a50", "a95", "breadth", "tail"]
    joined = oof.merge(frame[["file_id", *features]].reset_index(drop=True), on="file_id", validate="many_to_one")
    correlations = []
    # One correlation per repeat: do not pretend repeated file rows are independent.
    for (name, repeat), part in joined.groupby(["candidate", "repeat"]):
        for feature in features:
            rho = spearmanr(part[feature], part.log_residual).statistic if part[feature].nunique()>1 and part.log_residual.nunique()>1 else np.nan
            correlations.append(dict(candidate=name, repeat=repeat, feature=feature, spearman_rho=rho))
    pd.DataFrame(correlations).to_csv(output / "residual_correlations.csv", index=False)
    # Paired file-level differences relative to the metric-correct baseline.
    baseline = per[per.candidate == "weighted_median"][["file_id", "ape"]].rename(columns={"ape": "baseline_ape"})
    if len(baseline):
        pairs = per.merge(baseline, on="file_id", validate="many_to_one")
        pairs["ape_difference"] = pairs.ape-pairs.baseline_ape
        pairs.to_csv(output / "paired_baseline_differences.csv", index=False)
    write_json(output / "interpretation.json", dict(primary_metric="Mean APE over file-repeat appearances; each file equally weighted",
        splitting="Group-preserving; target balancing is overridden" if frame.group.nunique()<len(frame) else "Random file-level; target balancing follows the saved protocol",
        prediction_average_mape="Separate OOF prediction-average diagnostic; not the final refit's performance",
        uncertainty="Conditional 95% bootstrap sensitivity interval; not a guaranteed hidden-test confidence interval. File/group resampling; no refitting.",
        repeat_sd="Split sensitivity, not standard error; repeated predictions are dependent",
        residuals="Exploratory; adapting features after inspection makes reuse of this evaluation optimistic"))
    return summary


def save_parameter_summary(selections, output):
    rows = []
    for item in selections:
        c, state = item["candidate"], item["state"]
        row = dict(repeat=item["repeat"], fold=item["fold"], family=c["family"],
                   candidate=item["candidate_name"], m=c["m"], beta=c["beta"], alpha=c["alpha"])
        if "log_scale" in state:
            row["log_scale"] = state["log_scale"]
            row["scale"] = float(np.exp(state["log_scale"]))
        rows.append(row)
    table = pd.DataFrame(rows)
    table.to_csv(Path(output)/"selected_parameters.csv", index=False)
    table.family.value_counts().rename_axis("family").rename("outer_fits").to_csv(Path(output)/"family_frequencies.csv")
