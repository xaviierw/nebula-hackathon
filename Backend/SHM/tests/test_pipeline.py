"""Behavioral safeguards: parsing, mechanics, split boundaries and metric pooling."""
import numpy as np
import pandas as pd
import pytest
import rainflow

from data import (EXPONENTS, extract_file, extract_signal, fingerprints, logq_column,
                  mean_column, read_signal, validate_inventory, waveform_relationship)
from models import Candidate, FittedModel, fit_log_scale, fit_model
from splits import make_splits
from validation import nested_validation, select_candidate, summarise


def synthetic_frame(n=24):
    rng = np.random.default_rng(44)
    scale = np.exp(np.linspace(-1, 1, n))
    frame = pd.DataFrame(dict(file_id=[f"sample_{i}" for i in range(n)],
        group=[f"g{i}" for i in range(n)], sd=scale, cycle_count=np.full(n, 100.),
        breadth=rng.uniform(.1, 1, n), tail=rng.uniform(.1, .5, n)))
    for m in EXPONENTS:
        frame[logq_column(m)] = np.log(100.)+m*np.log(scale)
        frame[mean_column(m)] = rng.normal(0, 1, n)
    frame["damage"] = .002*np.exp(frame[logq_column(3)])
    return frame


def test_strict_parsing():
    np.testing.assert_array_equal(read_signal(b"1.5\n-2\n3\n", 3), [1.5, -2, 3])
    for raw in [b"stress\n1\n2\n", b"1,2\n3,4\n5,6\n", b"1\nNaN\n3\n",
                b"1\ninf\n3\n", b"1\n\n3\n", b"1\n2\n"]:
        with pytest.raises((ValueError, pd.errors.ParserError)):
            read_signal(raw, 3)


def test_inventory_uses_filename_not_row_order(tmp_path):
    (tmp_path/"Train").mkdir(); (tmp_path/"Test").mkdir()
    for i in range(1, 65):
        (tmp_path/"Train"/f"train{i:02d}.csv").touch()
    for i in range(1, 17):
        (tmp_path/"Test"/f"test{i:02d}.csv").touch()
    labels = pd.DataFrame(dict(filename=[f"train{i:02d}.csv" for i in range(64, 0, -1)],
                               damage=np.arange(64, 0, -1)/100))
    labels.to_csv(tmp_path/"Train_Labels.csv", index=False)
    _, _, mapping = validate_inventory(tmp_path)
    assert mapping.loc["train01.csv"] == .01
    labels.loc[1, "filename"] = labels.loc[0, "filename"]
    labels.to_csv(tmp_path/"Train_Labels.csv", index=False)
    with pytest.raises(ValueError, match="duplicate"):
        validate_inventory(tmp_path)


def test_rainflow_known_nested_cycles_and_scaling():
    x = np.array([0., 3., 1., 2., 0.])
    assert [c[:3] for c in rainflow.extract_cycles(x)] == [(1., 1.5, 1.), (3., 1.5, .5), (3., 1.5, .5)]
    a, shifted, scaled = extract_signal(x), extract_signal(x+7), extract_signal(x*2)
    assert a["cycle_records"] == 3 and a["cycle_count"] == 2
    for m in [1., 3., 12.]:
        assert np.isclose(a[logq_column(m)], shifted[logq_column(m)])
        assert np.isclose(scaled[logq_column(m)]-a[logq_column(m)], m*np.log(2))
        assert np.isclose(shifted[mean_column(m)]-a[mean_column(m)], 7)
    assert np.isclose(np.exp(a[logq_column(3)]), .5**3+1.5**3)


def test_content_cache_invalidates_and_overlap_is_shift_invariant(tmp_path):
    p = tmp_path/"signal.csv"
    p.write_text("0\n3\n1\n2\n0\n")
    first = extract_file(p, tmp_path/"cache", 5)
    p.write_text("0\n6\n2\n4\n0\n")
    second = extract_file(p, tmp_path/"cache", 5)
    assert first["sha256"] != second["sha256"]
    assert np.isclose(second["features"]["amplitude_max"], 2*first["features"]["amplitude_max"])
    rng = np.random.default_rng(9)
    x = rng.normal(size=20000)
    a = dict(fingerprints(x))
    b = dict(fingerprints(np.r_[rng.normal(size=137), x]))
    common = set(a) & set(b)
    assert common and all(b[key]-a[key] == 137 for key in common)


def test_waveform_groups_require_shape_similarity_across_entire_record():
    rng = np.random.default_rng(818)
    a = rng.normal(size=8000)
    close = 2*a + 5 + rng.normal(scale=.02, size=len(a))
    unrelated = rng.normal(size=len(a))
    assert waveform_relationship(a, close)["creates_group"]
    assert not waveform_relationship(a, unrelated)["creates_group"]
    partial = close.copy()
    partial[:1000] = unrelated[:1000]
    assert not waveform_relationship(a, partial)["creates_group"]


def test_exact_mape_scale_and_range_amplitude_equivalence():
    q, y = np.array([1., 2., 5., 9.]), np.array([.1, .6, .8, 4.])
    logk = fit_log_scale(np.log(q), y)
    k = np.exp(logk)
    loss = np.mean(abs(y-k*q)/y)
    alternatives = np.linspace(0, 1, 10001)
    assert loss <= np.mean(abs(y[:, None]-q[:, None]*alternatives)/y[:, None], axis=0).min()+1e-12
    k_range = np.exp(fit_log_scale(np.log(q)+3*np.log(2), y))
    assert np.isclose(k_range*8, k)


@pytest.mark.parametrize("family", ["median", "weighted_median", "stress", "physics", "flexible", "small", "hybrid", "two_moment"])
def test_models_positive_portable_and_ignore_filename(family):
    frame = synthetic_frame()
    model = fit_model(Candidate(family), frame, frame.damage.to_numpy(), frame.group.to_numpy())
    restored = FittedModel.from_dict(model.to_dict())
    renamed = frame.copy()
    renamed["file_id"] = "identifier-is-not-a-feature"
    a, b = model.predict(frame), restored.predict(renamed)
    np.testing.assert_allclose(a, b)
    assert np.isfinite(a).all() and (a>0).all()
    if family == "physics":
        np.testing.assert_allclose(a, frame.damage)


def test_splits_cover_once_and_preserve_groups():
    y = np.exp(np.linspace(-3, 1, 64))
    for balanced in [True, False]:
        groups = np.repeat(np.arange(16), 4)
        folds = make_splits(y, 5, 17, balanced, groups)
        assert sorted(np.concatenate([v for _, v in folds])) == list(range(64))
        for t, v in folds:
            assert not set(groups[t]) & set(groups[v])
    # A continuous target with many ties must still split without class-size errors.
    assert len(make_splits(np.r_[np.ones(63), 2], 5)) == 5


def test_pooled_metric_and_repeated_prediction_average_differ():
    # Unequal folds: unweighted fold averaging gives the wrong answer.
    rows = []
    for repeat, prediction in enumerate([[.5, 2., 1.], [1.5, .5, 1.]]):
        for i, p in enumerate(prediction):
            rows.append(dict(candidate="a", repeat=repeat, fold=int(i>0), file_id=str(i),
                             group=str(i), target=1., prediction=p, ape=abs(1-p)))
    table, per, reps, folds = summarise(pd.DataFrame(rows), bootstrap=True)
    assert np.isclose(table.iloc[0].mape, 2.5/6)
    assert np.isclose(table.iloc[0].prediction_average_mape, .25/3)
    assert table.iloc[0].files == 3
    assert table.iloc[0].resampling_units == 3
    assert table.iloc[0].score == 1-table.iloc[0].mape


def test_simplicity_rule_is_applied_after_inner_scores():
    cs = [Candidate("physics"), Candidate("small")]
    oof = pd.DataFrame(dict(candidate=[c.name for c in cs], ape=[.105, .1]))
    chosen, _ = select_candidate(oof, cs, .01)
    assert chosen.family == "physics"


def test_outer_labels_cannot_change_that_folds_selection_or_prediction():
    frame = synthetic_frame(24)
    cs = [Candidate("weighted_median"), Candidate("physics", m=3), Candidate("physics", m=5)]
    folds = make_splits(frame.damage, 5, 19, False, frame.group)
    _, val = folds[0]
    baseline, _, selections, _ = nested_validation(frame, cs, [19], 701, balanced=False)
    changed = frame.copy()
    changed.loc[val, "damage"] *= 100
    again, _, selections2, _ = nested_validation(changed, cs, [19], 701, balanced=False)
    # Unbalanced outer folds don't move with y. Its held-out labels must have
    # zero influence on inner selection and the fitted model for this fold.
    np.testing.assert_allclose(baseline[baseline.fold == 0].prediction, again[again.fold == 0].prediction)
    assert selections[0]["candidate"] == selections2[0]["candidate"]
    assert selections[0]["state"] == selections2[0]["state"]


def test_training_only_scaling_and_hybrid_crossfit(monkeypatch):
    import models
    frame = synthetic_frame()
    seen = []
    original = models.fit_log_scale
    def record(q, y):
        seen.append(len(y))
        return original(q, y)
    monkeypatch.setattr(models, "fit_log_scale", record)
    fit_model(Candidate("hybrid"), frame, frame.damage.to_numpy(), frame.group.to_numpy())
    assert len(seen) == 5
    assert seen[:4] == [18]*4  # Four training-only residual calibration fits.
    assert seen[-1] == 24


def test_nested_inner_membership_excludes_outer_files_and_groups():
    frame = synthetic_frame(24)
    frame["group"] = np.repeat(np.arange(8), 3)
    cs = [Candidate("weighted_median"), Candidate("physics")]
    _, records, _, _ = nested_validation(frame, cs, [81], 391)
    records = pd.DataFrame(records)
    group_by_file = frame.set_index("file_id").group
    for fold in records.loc[records.context == "outer", "fold"].unique():
        outer = records[(records.context == "outer") & (records.fold == fold)]
        inner = records[(records.context != "outer") & (records.outer_fold == fold)]
        assert not set(outer.file_id) & set(inner.file_id)
        assert not set(group_by_file.loc[outer.file_id]) & set(group_by_file.loc[inner.file_id])
