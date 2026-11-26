"""Statistics for analysing A/B tests: SRM, proportion and mean tests, CUPED, power, peeking."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import stats as st


@dataclass(frozen=True)
class Estimate:
    """A treatment-minus-control difference with its confidence interval."""

    estimate: float
    ci_low: float
    ci_high: float
    p_value: float
    std_error: float

    def contains(self, value: float) -> bool:
        return self.ci_low <= value <= self.ci_high


def _z_crit(alpha: float) -> float:
    return float(st.norm.ppf(1 - alpha / 2))


def srm_check(n_control: int, n_treatment: int, treatment_share: float = 0.5) -> float:
    """Sample ratio mismatch: p-value that the split matches the planned share.

    A tiny p-value (say < 0.001) means assignment or logging is broken, and the
    test results shouldn't be trusted until that's explained.
    """
    total = n_control + n_treatment
    expected = [total * (1 - treatment_share), total * treatment_share]
    return float(st.chisquare([n_control, n_treatment], expected).pvalue)


def two_proportion_test(
    x_control: int, n_control: int, x_treatment: int, n_treatment: int, alpha: float = 0.05
) -> Estimate:
    """Difference in conversion rates (treatment - control).

    The p-value uses the pooled standard error (the null says the rates are equal);
    the confidence interval uses the unpooled one.
    """
    p_c = x_control / n_control
    p_t = x_treatment / n_treatment
    diff = p_t - p_c

    p_pool = (x_control + x_treatment) / (n_control + n_treatment)
    se_pool = math.sqrt(p_pool * (1 - p_pool) * (1 / n_control + 1 / n_treatment))
    p_value = 2 * st.norm.sf(abs(diff) / se_pool) if se_pool > 0 else 1.0

    se = math.sqrt(p_c * (1 - p_c) / n_control + p_t * (1 - p_t) / n_treatment)
    z = _z_crit(alpha)
    return Estimate(diff, diff - z * se, diff + z * se, float(p_value), se)


def mean_difference(y_control: np.ndarray, y_treatment: np.ndarray, alpha: float = 0.05) -> Estimate:
    """Welch's t-test for a difference in means (treatment - control)."""
    y_c = np.asarray(y_control, dtype=float)
    y_t = np.asarray(y_treatment, dtype=float)
    v_c = y_c.var(ddof=1) / len(y_c)
    v_t = y_t.var(ddof=1) / len(y_t)
    se = math.sqrt(v_c + v_t)
    diff = y_t.mean() - y_c.mean()
    dof = (v_c + v_t) ** 2 / (v_c**2 / (len(y_c) - 1) + v_t**2 / (len(y_t) - 1))
    t_crit = float(st.t.ppf(1 - alpha / 2, dof))
    p_value = float(2 * st.t.sf(abs(diff) / se, dof))
    return Estimate(float(diff), diff - t_crit * se, diff + t_crit * se, p_value, se)


def cuped_adjust(y: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, float]:
    """CUPED: remove the part of y explained by a pre-experiment covariate x.

    theta = cov(x, y) / var(x), estimated on both arms together. Because x was
    measured before assignment, the adjustment can't bias the treatment effect,
    but it can shrink the variance a lot when x and y are correlated.
    """
    y = np.asarray(y, dtype=float)
    x = np.asarray(x, dtype=float)
    theta = float(np.cov(x, y, ddof=1)[0, 1] / x.var(ddof=1))
    return y - theta * (x - x.mean()), theta


def required_sample_size_proportions(
    baseline: float, mde_abs: float, alpha: float = 0.05, power: float = 0.8
) -> int:
    """Users needed per arm to detect an absolute lift of mde_abs over baseline."""
    p1, p2 = baseline, baseline + mde_abs
    p_bar = (p1 + p2) / 2
    z_a = _z_crit(alpha)
    z_b = float(st.norm.ppf(power))
    numerator = (
        z_a * math.sqrt(2 * p_bar * (1 - p_bar)) + z_b * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    ) ** 2
    return math.ceil(numerator / mde_abs**2)


def peeking_false_positive_rate(
    n_per_arm: int,
    looks: int,
    n_sims: int = 2_000,
    base_rate: float = 0.05,
    alpha: float = 0.05,
    seed: int = 0,
) -> float:
    """Share of A/A tests (no real effect) declared significant if you check `looks` times
    and stop at the first significant result. With one look this is about alpha."""
    rng = np.random.default_rng(seed)
    checkpoints = np.linspace(n_per_arm / looks, n_per_arm, looks).astype(int)
    increments = np.diff(np.concatenate([[0], checkpoints]))

    x_c = rng.binomial(increments, base_rate, size=(n_sims, looks)).cumsum(axis=1)
    x_t = rng.binomial(increments, base_rate, size=(n_sims, looks)).cumsum(axis=1)

    pooled = (x_c + x_t) / (2 * checkpoints)
    se = np.sqrt(pooled * (1 - pooled) * 2 / checkpoints)
    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.where(se > 0, (x_t - x_c) / checkpoints / se, 0.0)
    return float((np.abs(z) > _z_crit(alpha)).any(axis=1).mean())
