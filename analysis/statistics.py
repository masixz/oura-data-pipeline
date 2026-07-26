"""Statistical helpers for honest inference on autocorrelated daily data.

Sleep data breaks the assumption every off-the-shelf test makes: consecutive
nights are not independent draws. A plain Welch t-test on two contiguous
blocks of nights treats n = 150 as 150 independent observations when the
effective count is a fraction of that, which inflates significance. The
functions here exist to state effects honestly instead:

- `effective_n`      how many independent observations a series really carries
- `welch_t_effective` Welch t-test rescaled to that effective count
- `block_bootstrap_ci` CI for a difference in means, preserving serial structure
- `cohens_d`         effect size, which survives the autocorrelation objection
- `bh_fdr`           Benjamini-Hochberg adjustment across a test inventory
- `pearson_ci`       Fisher-z interval for a correlation
- `min_detectable_r` the smallest correlation a null result can rule out
- `within_week_deviations` strip slow drift before correlating two slow series
- `weekly_contrast`  day-of-week effects tested against the week they sit in

Which correction a claim needs depends on the shape of the comparison, and
getting this backwards is easy:

- Comparing two *time periods* (the 2024 dip) or fitting a *trend*: the
  autocorrelation penalty is real. Slow drift is exactly the confound, so
  `effective_n`, `welch_t_effective` and `block_bootstrap_ci` apply.
- Comparing days *within* a week (the Sunday-night effect): the penalty is
  misleading. Seasonal drift inflates within-group autocorrelation but
  cancels out of a within-week contrast, so a naive effective-n adjustment
  discards a real effect. Use `weekly_contrast` instead.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

__all__ = [
    "bh_fdr",
    "block_bootstrap_ci",
    "cohens_d",
    "effective_n",
    "min_detectable_r",
    "pearson_ci",
    "weekly_contrast",
    "welch_t_effective",
    "within_week_deviations",
]


def bh_fdr(pvalues) -> np.ndarray:
    """Benjamini-Hochberg adjusted p-values, in the input order.

    Controls the expected proportion of false discoveries among the rejected
    hypotheses. Preferred over Bonferroni here: the tests share a dataset and
    are far from independent, so Bonferroni is needlessly conservative.
    """
    p = np.asarray(pvalues, dtype=float)
    if p.ndim != 1 or p.size == 0:
        raise ValueError("pvalues must be a non-empty 1-D sequence")
    if np.any(~np.isfinite(p)) or np.any(p < 0) or np.any(p > 1):
        raise ValueError("pvalues must all lie in [0, 1]")

    m = p.size
    order = np.argsort(p)
    ranks = np.arange(1, m + 1)
    scaled = p[order] * m / ranks
    # Step-up: enforce monotonicity from the largest p downwards.
    adjusted = np.minimum.accumulate(scaled[::-1])[::-1]
    out = np.empty(m, dtype=float)
    out[order] = np.clip(adjusted, 0.0, 1.0)
    return out


def effective_n(x, max_lag: int | None = None) -> float:
    """Independent-observation count of a serially correlated series.

    Uses the initial-positive-sequence estimator of the integrated
    autocorrelation time: tau = 1 + 2 * sum(rho_k) truncated at the first
    non-positive rho_k, then n_eff = n / tau. For white noise tau = 1 and
    n_eff = n; for strongly persistent data n_eff can be several times
    smaller than n.
    """
    a = np.asarray(x, dtype=float)
    a = a[np.isfinite(a)]
    n = a.size
    if n < 3:
        return float(n)

    a = a - a.mean()
    denom = np.dot(a, a)
    if denom == 0:
        return float(n)

    if max_lag is None:
        max_lag = min(n - 2, max(10, n // 4))

    tau = 1.0
    for lag in range(1, max_lag + 1):
        rho = np.dot(a[:-lag], a[lag:]) / denom
        if rho <= 0:
            break
        tau += 2.0 * rho

    return float(np.clip(n / tau, 1.0, n))


def welch_t_effective(a, b) -> dict:
    """Welch t-test with both samples rescaled to their effective n.

    Returns the naive result alongside the corrected one so the cost of the
    independence assumption is visible rather than hidden.
    """
    x = np.asarray(a, dtype=float)
    y = np.asarray(b, dtype=float)
    x = x[np.isfinite(x)]
    y = y[np.isfinite(y)]

    t_naive, p_naive = stats.ttest_ind(x, y, equal_var=False)

    n1, n2 = effective_n(x), effective_n(y)
    v1, v2 = x.var(ddof=1), y.var(ddof=1)
    se = np.sqrt(v1 / n1 + v2 / n2)
    diff = x.mean() - y.mean()

    if se == 0:
        t_eff, p_eff, df = np.nan, np.nan, np.nan
    else:
        t_eff = diff / se
        # Welch-Satterthwaite on the effective counts.
        df = (v1 / n1 + v2 / n2) ** 2 / (
            (v1 / n1) ** 2 / max(n1 - 1, 1) + (v2 / n2) ** 2 / max(n2 - 1, 1)
        )
        p_eff = 2 * stats.t.sf(abs(t_eff), df)

    return {
        "diff": float(diff),
        "n_raw": (int(x.size), int(y.size)),
        "n_eff": (float(n1), float(n2)),
        "t_naive": float(t_naive),
        "p_naive": float(p_naive),
        "t_eff": float(t_eff),
        "p_eff": float(p_eff),
        "df_eff": float(df),
    }


def block_bootstrap_ci(
    a,
    b,
    block: int = 30,
    n_boot: int = 10_000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float]:
    """Moving-block bootstrap CI for mean(a) - mean(b).

    Resampling whole contiguous blocks keeps the within-block serial
    correlation intact, so the interval widens to something honest instead of
    the artificially tight one an i.i.d. bootstrap produces. `block` should
    comfortably exceed the correlation length of the series.
    """
    x = np.asarray(a, dtype=float)
    y = np.asarray(b, dtype=float)
    x = x[np.isfinite(x)]
    y = y[np.isfinite(y)]
    rng = np.random.default_rng(seed)

    def resample(series: np.ndarray) -> np.ndarray:
        n = series.size
        size = min(block, n)
        n_blocks = int(np.ceil(n / size))
        starts = rng.integers(0, n - size + 1, size=n_blocks)
        return np.concatenate([series[s : s + size] for s in starts])[:n]

    diffs = np.array([resample(x).mean() - resample(y).mean() for _ in range(n_boot)])
    lo, hi = np.percentile(diffs, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def cohens_d(a, b) -> dict:
    """Standardised mean difference with a normal-approximation 95% CI.

    Reported next to every t-test: an effect size does not shrink when the
    independence assumption is relaxed, so it is the durable part of a claim.
    """
    x = np.asarray(a, dtype=float)
    y = np.asarray(b, dtype=float)
    x = x[np.isfinite(x)]
    y = y[np.isfinite(y)]
    n1, n2 = x.size, y.size
    if n1 < 2 or n2 < 2:
        raise ValueError("both samples need at least 2 observations")

    pooled = np.sqrt(
        ((n1 - 1) * x.var(ddof=1) + (n2 - 1) * y.var(ddof=1)) / (n1 + n2 - 2)
    )
    d = (x.mean() - y.mean()) / pooled if pooled else np.nan
    se = np.sqrt((n1 + n2) / (n1 * n2) + d**2 / (2 * (n1 + n2 - 2)))
    return {"d": float(d), "ci": (float(d - 1.96 * se), float(d + 1.96 * se))}


def pearson_ci(r: float, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Fisher z-transform confidence interval for a correlation."""
    if n < 4:
        raise ValueError("need n >= 4 for a Fisher z interval")
    z = np.arctanh(np.clip(r, -0.999999, 0.999999))
    se = 1.0 / np.sqrt(n - 3)
    crit = stats.norm.ppf(1 - alpha / 2)
    return float(np.tanh(z - crit * se)), float(np.tanh(z + crit * se))


def within_week_deviations(series: pd.Series) -> pd.Series:
    """Deviation of each observation from the mean of its calendar week.

    Removes anything varying more slowly than a week: season, training blocks,
    the 2024 dip, hardware changes. What survives is the fast within-week
    signal, which is where day-of-week questions live. Correlating two
    deviation series avoids crediting shared slow drift as a relationship.
    """
    if not isinstance(series.index, pd.DatetimeIndex):
        raise TypeError("series must have a DatetimeIndex")
    week = series.index.to_period("W")
    return series - series.groupby(week).transform("mean")


def weekly_contrast(
    series: pd.Series,
    days: list[int],
    n_perm: int = 20_000,
    n_boot: int = 10_000,
    seed: int = 42,
) -> dict:
    """Test a day-of-week effect against the week each observation sits in.

    `days` holds Monday=0 weekday numbers. Restricted to complete 7-day weeks
    so every week contributes the same shape. Three results, no distributional
    assumptions beyond exchangeability of days within a week:

    - `observed`: mean over weeks of (mean of `days`) - (week mean)
    - `p_perm`:   permutation p from reassigning which positions are picked,
                  keeping every week's values intact
    - `ci`:       bootstrap interval resampling whole weeks, the independent unit
    """
    if not isinstance(series.index, pd.DatetimeIndex):
        raise TypeError("series must have a DatetimeIndex")
    if not days or not all(0 <= d <= 6 for d in days):
        raise ValueError("days must be a non-empty list of weekday numbers 0-6")

    s = series.dropna().sort_index()
    weeks = [g for _, g in s.groupby(s.index.to_period("W")) if len(g) == 7]
    if len(weeks) < 10:
        raise ValueError(f"only {len(weeks)} complete weeks, too few to test")

    k = len(days)
    blocks = [g.sort_index().values for g in weeks]
    picks = np.array([b[days].mean() - b.mean() for b in blocks])
    observed = float(picks.mean())

    rng = np.random.default_rng(seed)
    null = np.array([
        np.mean([b[rng.permutation(7)[:k]].mean() - b.mean() for b in blocks])
        for _ in range(n_perm)
    ])
    # Two-sided: how often does a random day selection deviate this far?
    p_perm = float((np.sum(np.abs(null) >= abs(observed)) + 1) / (n_perm + 1))

    boots = np.array([rng.choice(picks, picks.size).mean() for _ in range(n_boot)])
    lo, hi = np.percentile(boots, [2.5, 97.5])

    return {
        "observed": observed,
        "p_perm": p_perm,
        "ci": (float(lo), float(hi)),
        "n_weeks": len(blocks),
    }


def min_detectable_r(n: int, power: float = 0.8, alpha: float = 0.05) -> float:
    """Smallest correlation detectable at the given power.

    The number that turns "no effect found" into "any effect larger than this
    would have been found". Without it a null result is only an absence of
    evidence.
    """
    if n < 4:
        raise ValueError("need n >= 4")
    z_alpha = stats.norm.ppf(1 - alpha / 2)
    z_power = stats.norm.ppf(power)
    return float(np.tanh((z_alpha + z_power) / np.sqrt(n - 3)))
