import numpy as np
import pytest

from funnel_lab.experiments import stats
from funnel_lab.experiments.simulate import CONTROL, TREATMENT, PaywallTruth, simulate_paywall_meter


def test_sample_size_matches_textbook_value():
    # 10% -> 12%, alpha 0.05 two-sided, 80% power: 3,841 per arm
    assert stats.required_sample_size_proportions(0.10, 0.02) == 3841


def test_srm_flags_a_broken_split_and_passes_a_fair_one():
    assert stats.srm_check(50_000, 48_000) < 1e-6
    assert stats.srm_check(50_000, 50_100) > 0.05


def test_two_proportion_test_known_values():
    est = stats.two_proportion_test(100, 1000, 130, 1000)
    assert est.estimate == pytest.approx(0.03)
    assert est.p_value == pytest.approx(0.0353, abs=1e-3)
    assert est.ci_low < 0.03 < est.ci_high


def test_conversion_ci_recovers_simulated_truth():
    truth = PaywallTruth()
    df = simulate_paywall_meter(n_users=200_000, truth=truth, seed=1)
    c, t = df[df.variant == CONTROL], df[df.variant == TREATMENT]
    est = stats.two_proportion_test(c.subscribed.sum(), len(c), t.subscribed.sum(), len(t))
    assert est.contains(truth.absolute_lift)
    assert est.p_value < 0.05


def test_cuped_keeps_the_effect_and_shrinks_the_variance():
    df = simulate_paywall_meter(n_users=40_000, seed=3)
    is_t = (df.variant == TREATMENT).to_numpy()
    raw = stats.mean_difference(df.articles_read[~is_t], df.articles_read[is_t])
    adjusted, theta = stats.cuped_adjust(df.articles_read, df.pre_period_articles_read)
    cuped = stats.mean_difference(adjusted[~is_t], adjusted[is_t])

    assert theta > 0
    assert cuped.estimate == pytest.approx(raw.estimate, abs=2 * raw.std_error)
    assert cuped.std_error < 0.7 * raw.std_error


def test_welch_matches_scipy():
    from scipy import stats as st

    rng = np.random.default_rng(0)
    a, b = rng.normal(0, 1, 300), rng.normal(0.2, 2, 200)
    ours = stats.mean_difference(a, b)
    theirs = st.ttest_ind(b, a, equal_var=False)
    assert ours.p_value == pytest.approx(theirs.pvalue)


def test_peeking_inflates_false_positives():
    one_look = stats.peeking_false_positive_rate(2_000, looks=1, n_sims=4_000, seed=11)
    many_looks = stats.peeking_false_positive_rate(2_000, looks=10, n_sims=4_000, seed=11)
    assert 0.035 < one_look < 0.065
    assert many_looks > 0.12
