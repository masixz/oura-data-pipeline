"""Tests for the statistical helpers.

Run: .venv/bin/pytest
Pure functions, no database needed.
"""

import numpy as np
import pandas as pd
import pytest

from analysis.statistics import (
    bh_fdr,
    block_bootstrap_ci,
    cohens_d,
    effective_n,
    min_detectable_r,
    pearson_ci,
    weekly_contrast,
    welch_t_effective,
    within_week_deviations,
)


def ar1(n, rho, seed=0, scale=1.0):
    """AR(1) series: the simplest stand-in for autocorrelated daily data."""
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, scale, n)
    out = np.empty(n)
    out[0] = noise[0]
    for i in range(1, n):
        out[i] = rho * out[i - 1] + noise[i]
    return out


# --- bh_fdr --------------------------------------------------------------

def test_bh_fdr_known_case():
    # p * m / rank is a flat 0.05 for this ladder, so every value adjusts to 0.05
    adj = bh_fdr([0.01, 0.02, 0.03, 0.04, 0.05])
    assert np.allclose(adj, 0.05)


def test_bh_fdr_keeps_input_order():
    adj = bh_fdr([0.5, 0.001])
    assert adj[1] < adj[0]
    assert adj[1] == pytest.approx(0.002)


def test_bh_fdr_is_monotone_in_p():
    p = np.array([0.001, 0.01, 0.2, 0.4, 0.9])
    adj = bh_fdr(p)
    assert np.all(np.diff(adj) >= 0)


def test_bh_fdr_never_exceeds_one():
    assert np.all(bh_fdr([0.9, 0.95, 0.99]) <= 1.0)


def test_bh_fdr_only_weakens_evidence():
    p = np.array([0.001, 0.02, 0.3])
    assert np.all(bh_fdr(p) >= p)


def test_bh_fdr_rejects_bad_input():
    with pytest.raises(ValueError):
        bh_fdr([])
    with pytest.raises(ValueError):
        bh_fdr([0.5, 1.5])
    with pytest.raises(ValueError):
        bh_fdr([0.5, np.nan])


# --- effective_n ---------------------------------------------------------

def test_effective_n_of_white_noise_is_near_n():
    x = np.random.default_rng(1).normal(size=2000)
    assert effective_n(x) > 0.8 * len(x)


def test_effective_n_shrinks_under_autocorrelation():
    x = ar1(2000, rho=0.9, seed=2)
    n_eff = effective_n(x)
    assert n_eff < 0.25 * len(x)  # theory: tau = (1+rho)/(1-rho) = 19
    assert n_eff >= 1.0


def test_effective_n_more_correlation_means_fewer_observations():
    mild = effective_n(ar1(2000, rho=0.3, seed=3))
    heavy = effective_n(ar1(2000, rho=0.95, seed=3))
    assert heavy < mild


def test_effective_n_handles_degenerate_input():
    assert effective_n([1.0, 2.0]) == 2.0
    assert effective_n(np.ones(50)) == 50.0


# --- welch_t_effective ---------------------------------------------------

def test_welch_effective_penalises_autocorrelated_samples():
    a = ar1(400, rho=0.9, seed=4) + 0.5
    b = ar1(400, rho=0.9, seed=5)
    res = welch_t_effective(a, b)
    assert res["n_eff"][0] < res["n_raw"][0]
    assert res["p_eff"] > res["p_naive"]  # honest p-value is the larger one
    assert abs(res["t_eff"]) < abs(res["t_naive"])


def test_welch_effective_matches_naive_on_white_noise():
    rng = np.random.default_rng(6)
    a, b = rng.normal(0.4, 1, 800), rng.normal(0, 1, 800)
    res = welch_t_effective(a, b)
    assert res["p_eff"] == pytest.approx(res["p_naive"], abs=0.05)


def test_welch_effective_reports_the_raw_difference():
    res = welch_t_effective([10.0, 12.0, 14.0], [1.0, 3.0, 5.0])
    assert res["diff"] == pytest.approx(9.0)


# --- block_bootstrap_ci --------------------------------------------------

def test_block_bootstrap_ci_brackets_the_observed_difference():
    # A percentile bootstrap CI is centred on the sample difference, not the
    # population one, so this is the property that must hold every time.
    a = ar1(500, rho=0.8, seed=7) + 2.0
    b = ar1(500, rho=0.8, seed=8)
    lo, hi = block_bootstrap_ci(a, b, block=30, n_boot=1000)
    assert lo < (a.mean() - b.mean()) < hi


def test_block_bootstrap_ci_covers_the_true_difference_across_trials():
    # Coverage measured at 0.90-0.92 against a nominal 0.95: block bootstraps
    # under-cover slightly on AR(1) data. Asserted loosely so this cannot flake.
    hits = 0
    trials = 40
    for s in range(trials):
        a = ar1(500, rho=0.8, seed=1000 + 2 * s) + 2.0
        b = ar1(500, rho=0.8, seed=1001 + 2 * s)
        lo, hi = block_bootstrap_ci(a, b, block=30, n_boot=600)
        hits += lo < 2.0 < hi
    assert hits / trials >= 0.80


def test_block_bootstrap_ci_is_wider_than_iid_blocks():
    a = ar1(500, rho=0.9, seed=9)
    b = ar1(500, rho=0.9, seed=10)
    wide = block_bootstrap_ci(a, b, block=50, n_boot=1000)
    narrow = block_bootstrap_ci(a, b, block=1, n_boot=1000)
    assert (wide[1] - wide[0]) > (narrow[1] - narrow[0])


def test_block_bootstrap_ci_is_reproducible():
    a, b = ar1(200, rho=0.5, seed=11), ar1(200, rho=0.5, seed=12)
    assert block_bootstrap_ci(a, b, n_boot=500) == block_bootstrap_ci(a, b, n_boot=500)


# --- cohens_d ------------------------------------------------------------

def test_cohens_d_recovers_a_known_effect():
    rng = np.random.default_rng(13)
    a, b = rng.normal(1.0, 1.0, 5000), rng.normal(0.0, 1.0, 5000)
    res = cohens_d(a, b)
    assert res["d"] == pytest.approx(1.0, abs=0.1)
    assert res["ci"][0] < res["d"] < res["ci"][1]


def test_cohens_d_is_zero_for_identical_samples():
    x = np.arange(100, dtype=float)
    assert cohens_d(x, x)["d"] == pytest.approx(0.0)


def test_cohens_d_needs_two_observations():
    with pytest.raises(ValueError):
        cohens_d([1.0], [2.0, 3.0])


# --- pearson_ci ----------------------------------------------------------

def test_pearson_ci_contains_the_estimate():
    lo, hi = pearson_ci(0.8, 1200)
    assert lo < 0.8 < hi


def test_pearson_ci_tightens_with_more_data():
    small = pearson_ci(0.5, 30)
    large = pearson_ci(0.5, 3000)
    assert (large[1] - large[0]) < (small[1] - small[0])


def test_pearson_ci_stays_within_bounds():
    lo, hi = pearson_ci(0.99, 10)
    assert -1.0 <= lo <= hi <= 1.0


# --- min_detectable_r ----------------------------------------------------

def test_min_detectable_r_at_the_projects_sample_size():
    # ~1200 nights: anything above a weak correlation would have been caught
    assert min_detectable_r(1200) == pytest.approx(0.081, abs=0.005)


def test_min_detectable_r_falls_as_n_grows():
    assert min_detectable_r(5000) < min_detectable_r(500) < min_detectable_r(50)


def test_min_detectable_r_rises_with_required_power():
    assert min_detectable_r(1000, power=0.95) > min_detectable_r(1000, power=0.8)


# --- within_week_deviations ----------------------------------------------

def daily_series(n, values):
    return pd.Series(values, index=pd.date_range("2023-01-02", periods=n, freq="D"))


def test_within_week_deviations_removes_slow_drift():
    n = 700
    rng = np.random.default_rng(20)
    trend = np.linspace(0, 50, n)  # huge slow drift
    fast = rng.normal(0, 1, n)
    with_drift = within_week_deviations(daily_series(n, trend + fast))
    without = within_week_deviations(daily_series(n, fast))
    # Nearly identical, but not exactly: subtracting the week mean removes
    # drift *between* weeks and leaves the ramp *inside* each week, which here
    # spans 0.5 against a noise sd of 1.0. Anything above 0.98 means the fast
    # signal dominates what survives.
    assert np.corrcoef(with_drift, without)[0, 1] > 0.98
    # Sanity check the drift really was large enough to matter before removal
    assert daily_series(n, trend + fast).std() > 10


def test_within_week_deviations_are_zero_for_a_flat_week():
    s = daily_series(14, np.r_[np.ones(7) * 5, np.ones(7) * 99])
    assert np.allclose(within_week_deviations(s), 0.0)


def test_within_week_deviations_requires_datetime_index():
    with pytest.raises(TypeError):
        within_week_deviations(pd.Series([1.0, 2.0, 3.0]))


# --- weekly_contrast -----------------------------------------------------

def series_with_weekday_effect(n=560, day=0, effect=-3.0, drift=40.0, seed=21):
    """Slow drift plus a genuine penalty on one weekday."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-02", periods=n, freq="D")  # starts on a Monday
    values = np.linspace(0, drift, n) + rng.normal(0, 2.0, n)
    values[idx.dayofweek == day] += effect
    return pd.Series(values, index=idx)


def test_weekly_contrast_recovers_a_planted_weekday_effect():
    s = series_with_weekday_effect(effect=-3.0)
    res = weekly_contrast(s, [0], n_perm=4000, n_boot=2000)
    # A -3 hit on one day of seven shows up as -3 * 6/7 against the week mean
    assert res["observed"] == pytest.approx(-3.0 * 6 / 7, abs=0.5)
    assert res["p_perm"] < 0.01
    assert res["ci"][1] < 0


def test_weekly_contrast_survives_drift_that_defeats_the_naive_test():
    # The methodological point: a big slow trend makes the two-sample
    # effective-n test discard a real within-week effect, while the
    # within-week contrast still finds it.
    s = series_with_weekday_effect(effect=-3.0, drift=60.0)
    naive = welch_t_effective(s[s.index.dayofweek == 0], s[s.index.dayofweek != 0])
    contrast = weekly_contrast(s, [0], n_perm=4000, n_boot=2000)
    assert naive["p_eff"] > 0.05  # naive test misses it
    assert contrast["p_perm"] < 0.01  # within-week contrast keeps it


def test_weekly_contrast_finds_nothing_when_there_is_nothing():
    s = series_with_weekday_effect(effect=0.0)
    res = weekly_contrast(s, [0], n_perm=4000, n_boot=2000)
    assert res["p_perm"] > 0.05
    assert res["ci"][0] < 0 < res["ci"][1]


def test_weekly_contrast_handles_multi_day_selections():
    s = series_with_weekday_effect(day=5, effect=-4.0)
    s[s.index.dayofweek == 6] -= 4.0  # both weekend days penalised
    res = weekly_contrast(s, [5, 6], n_perm=4000, n_boot=2000)
    assert res["observed"] < -1.5
    assert res["p_perm"] < 0.01


def test_weekly_contrast_counts_only_complete_weeks():
    s = series_with_weekday_effect(n=560)
    res = weekly_contrast(s, [0], n_perm=500, n_boot=500)
    assert res["n_weeks"] <= 560 // 7


def test_weekly_contrast_rejects_bad_input():
    s = series_with_weekday_effect()
    with pytest.raises(ValueError):
        weekly_contrast(s, [])
    with pytest.raises(ValueError):
        weekly_contrast(s, [9])
    with pytest.raises(ValueError):
        weekly_contrast(s.head(21), [0])  # too few complete weeks
    with pytest.raises(TypeError):
        weekly_contrast(pd.Series([1.0] * 100), [0])
