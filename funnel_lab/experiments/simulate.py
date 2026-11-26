"""Simulate a paywall meter A/B test with a known true effect.

Control gets 5 free articles before the paywall, treatment gets 3. Treatment readers
hit the paywall sooner, so they read a little less and subscribe a little more.
Because we set those effects here, the analysis can be checked against the truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

CONTROL = "control"
TREATMENT = "treatment"


@dataclass(frozen=True)
class PaywallTruth:
    base_rate: float = 0.04  # control subscription rate
    relative_lift: float = 0.15  # treatment subscribes 15% more (relative)
    articles_effect: float = -0.08  # treatment reads 8% fewer articles

    @property
    def absolute_lift(self) -> float:
        return self.base_rate * self.relative_lift


TRUTH = PaywallTruth()


def simulate_paywall_meter(
    n_users: int = 40_000,
    truth: PaywallTruth = TRUTH,
    seed: int = 7,
    start: datetime = datetime(2021, 2, 1),
    days: int = 14,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    # Each reader has a latent engagement level (articles per two weeks).
    # Pre-period reading is a noisy measure of it, which is what makes CUPED work.
    engagement = rng.gamma(shape=1.2, scale=5.0, size=n_users)
    pre_period = rng.poisson(engagement)

    is_treatment = rng.random(n_users) < 0.5
    articles = rng.poisson(engagement * np.where(is_treatment, 1 + truth.articles_effect, 1.0))

    # More engaged readers are more likely to subscribe. Normalise so the
    # control rate averages truth.base_rate.
    propensity = np.log1p(engagement)
    propensity /= propensity.mean()
    p_subscribe = truth.base_rate * propensity * np.where(is_treatment, 1 + truth.relative_lift, 1.0)
    subscribed = rng.random(n_users) < np.clip(p_subscribe, 0, 1)

    offsets = rng.integers(0, days * 86_400, size=n_users)
    return pd.DataFrame(
        {
            "user_id": [f"u{i:07d}" for i in range(n_users)],
            "variant": np.where(is_treatment, TREATMENT, CONTROL),
            "assigned_at": [start + timedelta(seconds=int(s)) for s in offsets],
            "pre_period_articles_read": pre_period,
            "articles_read": articles,
            "subscribed": subscribed,
        }
    )
