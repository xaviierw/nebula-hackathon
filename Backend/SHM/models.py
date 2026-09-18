"""Small, positive fatigue models with training-only MAPE calibration."""
from dataclasses import asdict, dataclass

import numpy as np
from scipy.optimize import linprog
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from data import EXPONENTS, logq_column, mean_column, require
from splits import make_splits


@dataclass(frozen=True)
class Candidate:
    family: str
    m: float = 3.
    beta: float = 1.
    alpha: float = 10.

    @property
    def name(self):
        if self.family in {"median", "weighted_median", "two_moment"}:
            return self.family
        if self.family == "stress":
            return f"stress_p{self.m:g}"
        if self.family == "physics":
            return f"physics_m{self.m:g}"
        if self.family == "flexible":
            return f"flexible_m{self.m:g}_b{self.beta:g}"
        return f"{self.family}_m{self.m:g}_a{self.alpha:g}"

    @property
    def complexity(self):
        return {"median": 0, "weighted_median": 0, "stress": 1, "physics": 1,
                "flexible": 2, "two_moment": 2, "small": 3, "hybrid": 4}[self.family]


def candidates(include_hybrid=False):
    items = [Candidate("median"), Candidate("weighted_median")]
    items += [Candidate("stress", m=float(p)) for p in np.arange(1, 8.01, .5)]
    items += [Candidate("physics", m=m) for m in EXPONENTS]
    items += [Candidate("flexible", m=m, beta=b) for m in EXPONENTS for b in [.75, 1.25]]
    items += [Candidate("two_moment")]
    items += [Candidate("small", m=m, alpha=a) for m in [3., 5., 7.] for a in [1., 10., 100.]]
    if include_hybrid:
        items += [Candidate("hybrid", m=m, alpha=a) for m in [3., 5., 7.] for a in [1., 10., 100.]]
    return items


def weighted_median(values, weights):
    values, weights = np.asarray(values), np.asarray(weights)
    require(len(values) > 0 and np.isfinite(values).all(), "Invalid weighted-median values")
    require(np.isfinite(weights).all() and (weights >= 0).all() and weights.sum() > 0, "Invalid weights")
    order = np.argsort(values, kind="stable")
    index = np.searchsorted(np.cumsum(weights[order]), weights.sum()/2, side="left")
    return float(values[order[min(index, len(values)-1)]])


def fit_log_scale(log_basis, y):
    """Exact MAPE-optimal multiplier, using logs for numerical stability."""
    log_ratio = np.log(y)-log_basis
    log_weight = -log_ratio
    return weighted_median(log_ratio, np.exp(log_weight-log_weight.max()))


def positive_exp(log_prediction):
    with np.errstate(over="ignore", under="ignore"):
        prediction = np.exp(log_prediction)
    require(np.isfinite(prediction).all() and (prediction > 0).all(),
            "Nonpositive/nonfinite predictions: investigate the model; no silent clipping")
    return prediction


def compact_features(frame, m, hybrid=False):
    columns = ["breadth", "tail", mean_column(m)] if hybrid else [logq_column(m), "cycle_count", "breadth", "tail", mean_column(m)]
    x = frame[columns].to_numpy(dtype=float).copy()
    if not hybrid:
        x[:, 1] = np.log(x[:, 1])
    require(np.isfinite(x).all(), "Nonfinite compact features")
    return x


def fit_ridge(x, target, alpha):
    scaler = StandardScaler().fit(x)
    model = Ridge(alpha=alpha).fit(scaler.transform(x), target)
    return dict(mean=scaler.mean_.tolist(), scale=scaler.scale_.tolist(),
                coefficients=model.coef_.tolist(), intercept=float(model.intercept_))


def ridge_predict(state, x):
    return ((x-np.asarray(state["mean"]))/np.asarray(state["scale"])) @ np.asarray(state["coefficients"]) + state["intercept"]


@dataclass
class FittedModel:
    candidate: Candidate
    state: dict

    def to_dict(self):
        return dict(candidate=asdict(self.candidate), state=self.state)

    @classmethod
    def from_dict(cls, value):
        return cls(Candidate(**value["candidate"]), value["state"])

    def predict(self, frame):
        c, s = self.candidate, self.state
        if c.family in {"median", "weighted_median"}:
            logpred = np.full(len(frame), s["log_constant"])
        elif c.family == "stress":
            logpred = s["log_scale"] + c.m*np.log(frame.sd.to_numpy())
        elif c.family in {"physics", "flexible"}:
            logpred = s["log_scale"] + c.beta*frame[logq_column(c.m)].to_numpy()
        elif c.family == "small":
            logpred = ridge_predict(s["ridge"], compact_features(frame, c.m)) + s["log_scale"]
        elif c.family == "hybrid":
            logpred = s["log_scale"] + frame[logq_column(c.m)].to_numpy()
            logpred += ridge_predict(s["ridge"], compact_features(frame, c.m, hybrid=True))
        elif c.family == "two_moment":
            q = frame[[logq_column(3), logq_column(5)]].to_numpy()
            coefficients = np.asarray(s["coefficients"])
            active = coefficients > 0
            require(active.any(), "Two-moment fit has no positive coefficient")
            terms = q[:, active]-np.asarray(s["offsets"])[active]+np.log(coefficients[active])
            logpred = np.logaddexp.reduce(terms, axis=1)
        else:
            raise ValueError(f"Unknown model family {c.family}")
        return positive_exp(logpred)


def fit_model(candidate, frame, y, groups=None, seed=711):
    c = candidate
    y = np.asarray(y, dtype=float)
    require(len(frame) == len(y) and np.isfinite(y).all() and (y > 0).all(), "Invalid training labels")
    if c.family in {"median", "weighted_median"}:
        constant = np.median(y) if c.family == "median" else weighted_median(y, 1/y)
        state = dict(log_constant=float(np.log(constant)))
    elif c.family in {"physics", "flexible", "stress"}:
        basis = c.m*np.log(frame.sd.to_numpy()) if c.family == "stress" else c.beta*frame[logq_column(c.m)].to_numpy()
        state = dict(log_scale=fit_log_scale(basis, y))
    elif c.family == "small":
        x = compact_features(frame, c.m)
        ridge = fit_ridge(x, np.log(y), c.alpha)
        state = dict(ridge=ridge, log_scale=fit_log_scale(ridge_predict(ridge, x), y))
    elif c.family == "hybrid":
        # m and alpha are fixed components of this candidate, not globally tuned
        # parameters. All cross-fit calibration sees only its training labels.
        logq = frame[logq_column(c.m)].to_numpy()
        crossfit = np.full(len(y), np.nan)
        for train, val in make_splits(y, 4, seed, True, groups):
            crossfit[val] = logq[val] + fit_log_scale(logq[train], y[train])
        require(np.isfinite(crossfit).all(), "Incomplete residual cross-fitting")
        ridge = fit_ridge(compact_features(frame, c.m, hybrid=True), np.log(y)-crossfit, c.alpha)
        state = dict(ridge=ridge, log_scale=fit_log_scale(logq, y), residual_target="four_fold_cross_fitted_log_ratio")
    elif c.family == "two_moment":
        q = frame[[logq_column(3), logq_column(5)]].to_numpy()
        offsets = np.median(q, axis=0)
        design = np.exp(q-offsets)/y[:, None]
        n = len(y)
        # Minimise |prediction/y - 1| through nonnegative absolute-error slacks.
        constraints = np.vstack([np.column_stack([design, -np.eye(n)]),
                                 np.column_stack([-design, -np.eye(n)])])
        result = linprog(np.r_[np.zeros(2), np.ones(n)/n], A_ub=constraints,
                         b_ub=np.r_[np.ones(n), -np.ones(n)], bounds=(0, None), method="highs")
        require(result.success, f"Two-moment optimisation failed: {result.message}")
        state = dict(coefficients=result.x[:2].tolist(), offsets=offsets.tolist())
    else:
        raise ValueError(f"Unknown model family {c.family}")
    model = FittedModel(c, state)
    model.predict(frame)  # Check positivity before a fit can be saved.
    return model
