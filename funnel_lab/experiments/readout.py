"""Analyse the paywall meter test. Shared by the command-line readout and the dashboard."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from funnel_lab.experiments import stats
from funnel_lab.experiments.simulate import CONTROL, TREATMENT, TRUTH


@dataclass(frozen=True)
class Readout:
    control_users: int
    treatment_users: int
    srm_p_value: float
    control_rate: float
    treatment_rate: float
    conversion: stats.Estimate  # absolute difference in subscription rate
    relative_lift: float
    true_relative_lift: float
    true_absolute_lift: float
    articles_raw: stats.Estimate
    articles_cuped: stats.Estimate
    cuped_theta: float
    cuped_variance_reduction: float
    users_needed_per_arm: int
    peeking_looks: int
    peeking_false_positive_rate: float

    def to_dict(self) -> dict:
        return asdict(self)


def analyse(users: pd.DataFrame, peeking_looks: int = 14) -> Readout:
    """`users` has one row per user: variant, subscribed, articles_read, pre_period_articles_read."""
    is_t = (users.variant == TREATMENT).to_numpy()
    ctrl, trt = users[~is_t], users[is_t]

    conversion = stats.two_proportion_test(
        int(ctrl.subscribed.sum()), len(ctrl), int(trt.subscribed.sum()), len(trt)
    )
    control_rate = float(ctrl.subscribed.mean())

    raw = stats.mean_difference(ctrl.articles_read, trt.articles_read)
    adjusted, theta = stats.cuped_adjust(users.articles_read, users.pre_period_articles_read)
    cuped = stats.mean_difference(adjusted[~is_t], adjusted[is_t])

    n_needed = stats.required_sample_size_proportions(TRUTH.base_rate, TRUTH.absolute_lift)
    return Readout(
        control_users=len(ctrl),
        treatment_users=len(trt),
        srm_p_value=stats.srm_check(len(ctrl), len(trt)),
        control_rate=control_rate,
        treatment_rate=float(trt.subscribed.mean()),
        conversion=conversion,
        relative_lift=conversion.estimate / control_rate,
        true_relative_lift=TRUTH.relative_lift,
        true_absolute_lift=TRUTH.absolute_lift,
        articles_raw=raw,
        articles_cuped=cuped,
        cuped_theta=theta,
        cuped_variance_reduction=1 - (cuped.std_error / raw.std_error) ** 2,
        users_needed_per_arm=n_needed,
        peeking_looks=peeking_looks,
        peeking_false_positive_rate=stats.peeking_false_positive_rate(
            n_per_arm=n_needed, looks=peeking_looks, base_rate=TRUTH.base_rate
        ),
    )


__all__ = ["CONTROL", "TREATMENT", "Readout", "analyse"]
