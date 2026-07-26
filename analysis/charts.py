"""Generate README charts from the staging layer.

Run: python -m analysis.charts

Outputs PNGs to assets/. Only aggregated statistics are rendered — no raw
daily rows leave the database (see PRIVACY.md).
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
BLUE = "#2a78d6"

ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets")

plt.rcParams.update({
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "text.color": INK,
    "axes.edgecolor": INK_2,
    "axes.labelcolor": INK_2,
    "xtick.color": INK_2,
    "ytick.color": INK_2,
    "axes.grid": True,
    "grid.color": "#e6e5e1",
    "grid.linewidth": 0.6,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.size": 10,
})


ENGINE = create_engine(os.environ["DATABASE_URL"])


def q(sql: str) -> pd.DataFrame:
    return pd.read_sql(sql, ENGINE)


def chart_three_signals():
    df = q("""
        SELECT date_trunc('month', day)::date AS month,
               avg(sleep_score) AS sleep_score,
               avg(avg_hrv)     AS hrv,
               avg(lowest_hr)   AS lowest_hr
        FROM staging.daily
        GROUP BY 1 ORDER BY 1
    """)
    df["month"] = pd.to_datetime(df["month"])

    panels = [
        ("sleep_score", "Sleep score (monthly avg)"),
        ("hrv", "Average HRV, ms (monthly avg)"),
        ("lowest_hr", "Lowest night heart rate, bpm (monthly avg)"),
    ]
    fig, axes = plt.subplots(3, 1, figsize=(9, 7), sharex=True)
    for ax, (col, title) in zip(axes, panels):
        ax.plot(df["month"], df[col], color=BLUE, linewidth=2)
        ax.set_title(title, loc="left", fontsize=10, color=INK)
        ax.margins(x=0.01)

    fig.suptitle("Four years, three signals: the 2024 dip and the recovery",
                 x=0.01, ha="left", fontsize=13, color=INK, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = os.path.join(ASSETS, "three_signals.png")
    fig.savefig(out, dpi=150)
    print("wrote", out)


def chart_weekday():
    df = q("""
        SELECT extract(isodow FROM day)::int AS dow,
               avg(sleep_score) AS score
        FROM staging.daily
        GROUP BY 1 ORDER BY 1
    """)
    # Oura assigns sleep to the wake-up day: Mon = Sunday night
    labels = ["Sun night", "Mon night", "Tue night", "Wed night",
              "Thu night", "Fri night", "Sat night"]

    fig, ax = plt.subplots(figsize=(9, 4))
    # Point marks, not bars: a non-zero baseline is honest for points,
    # while truncated bars would exaggerate the differences.
    ax.plot(labels, df["score"], "o", color=BLUE, markersize=9)
    ax.set_title("Average sleep score by night of week",
                 loc="left", fontsize=13, color=INK, fontweight="bold")
    ax.set_ylim(65, 76)
    ax.grid(axis="x", visible=False)

    for i in range(len(df)):
        ax.annotate(f"{df['score'][i]:.1f}", (labels[i], df["score"][i]),
                    ha="center", va="bottom", fontsize=10, color=INK_2,
                    xytext=(0, 7), textcoords="offset points")

    fig.tight_layout()
    out = os.path.join(ASSETS, "weekday_scores.png")
    fig.savefig(out, dpi=150)
    print("wrote", out)


def chart_bedtime_cost():
    """The README headline: what a later bedtime costs, and timing vs consistency.

    Uses bedtime_start_local, the wall-clock time the ring recorded. Reading the
    hour off the UTC timestamp instead understates the effect and adds a fake
    seasonal swing as Finland moves between UTC+2 and UTC+3.
    """
    nights = q("""
        SELECT day, sleep_score,
               extract(hour FROM bedtime_start_local) * 60
             + extract(minute FROM bedtime_start_local) AS bedtime_min
        FROM staging.daily
        WHERE bedtime_start_local IS NOT NULL AND sleep_score IS NOT NULL
        ORDER BY day
    """)
    # Hours after 18:00, so an evening and the small hours sit on one axis
    m = nights["bedtime_min"].astype(float)
    nights["bedtime_h"] = np.where(m >= 18 * 60, m - 18 * 60, m + 6 * 60) / 60.0
    nights["day"] = pd.to_datetime(nights["day"])

    buckets = [
        ("before\n23:00", (0, 5)),
        ("23:00\nto 00:59", (5, 7)),
        ("01:00\nto 01:59", (7, 8)),
        ("02:00\nto 02:59", (8, 9)),
        ("03:00\nor later", (9, 14)),
    ]
    labels, means, counts = [], [], []
    for label, (lo, hi) in buckets:
        sel = nights[(nights.bedtime_h >= lo) & (nights.bedtime_h < hi)]
        labels.append(label)
        means.append(sel.sleep_score.mean())
        counts.append(len(sel))

    slope, intercept = np.polyfit(nights.bedtime_h, nights.sleep_score, 1)
    r = nights.bedtime_h.corr(nights.sleep_score)

    # Weekly timing vs consistency: the comparison the headline rests on
    weekly = (nights.set_index("day")
                    .groupby(pd.Grouper(freq="W"))
                    .agg(score=("sleep_score", "mean"),
                         timing=("bedtime_h", "mean"),
                         consistency=("bedtime_h", "std"),
                         nights=("bedtime_h", "size")))
    weekly = weekly[weekly.nights >= 5].dropna()
    r_timing = weekly.timing.corr(weekly.score)
    r_consistency = weekly.consistency.corr(weekly.score)

    def residual(a, b):
        return a - np.poly1d(np.polyfit(b, a, 1))(b)

    r_timing_adj = np.corrcoef(residual(weekly.timing.values, weekly.consistency.values),
                               residual(weekly.score.values, weekly.consistency.values))[0, 1]
    r_consistency_adj = np.corrcoef(residual(weekly.consistency.values, weekly.timing.values),
                                    residual(weekly.score.values, weekly.timing.values))[0, 1]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4), width_ratios=[1.35, 1])

    ax = axes[0]
    ax.plot(labels, means, "o", color=BLUE, markersize=11)
    for i, (mu, n) in enumerate(zip(means, counts)):
        ax.annotate(f"{mu:.1f}\nn={n}", (i, mu), ha="center", va="bottom",
                    xytext=(0, 9), textcoords="offset points",
                    fontsize=9, color=INK_2)
    ax.set_ylim(min(means) - 6, max(means) + 8)
    ax.set_ylabel("average sleep score")
    ax.set_title(f"Every hour later costs {abs(slope):.1f} sleep-score points",
                 loc="left", fontsize=13, color=INK, fontweight="bold")
    ax.grid(axis="x", visible=False)

    ax = axes[1]
    bars = ["timing\nalone", "consistency\nalone", "timing, holding\nconsistency fixed",
            "consistency, holding\ntiming fixed"]
    vals = [r_timing, r_consistency, r_timing_adj, r_consistency_adj]
    colors = [BLUE, INK_2, BLUE, INK_2]
    ax.barh(bars, vals, color=colors)
    ax.axvline(0, color=INK, linewidth=1)
    for i, v in enumerate(vals):
        ax.annotate(f"{v:+.2f}", (v, i), xytext=(-34 if v < -0.05 else 6, 0),
                    textcoords="offset points", va="center",
                    fontsize=9, color=INK_2)
    ax.set_xlim(-0.72, 0.28)
    ax.set_xlabel(f"correlation with weekly sleep score  ({len(weekly)} weeks)")
    ax.set_title("Timing carries it, not consistency",
                 loc="left", fontsize=12, color=INK, fontweight="bold")
    ax.grid(axis="y", visible=False)
    ax.invert_yaxis()

    fig.tight_layout()
    out = os.path.join(ASSETS, "bedtime_cost.png")
    fig.savefig(out, dpi=150)
    print("wrote", out)
    print(f"  nightly slope {slope:+.2f} pts/hour, r={r:+.3f}, n={len(nights)}")
    print(f"  weekly timing r={r_timing:+.3f} -> {r_timing_adj:+.3f} adjusted for consistency")
    print(f"  weekly consistency r={r_consistency:+.3f} -> {r_consistency_adj:+.3f} adjusted for timing")


if __name__ == "__main__":
    os.makedirs(ASSETS, exist_ok=True)
    chart_three_signals()
    chart_weekday()
    chart_bedtime_cost()
