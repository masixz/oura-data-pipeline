"""Generate README charts from the staging layer.

Run: python -m analysis.charts

Outputs PNGs to assets/. Only aggregated statistics are rendered — no raw
daily rows leave the database (see PRIVACY.md).
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
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

    lo, hi = df["score"].idxmin(), df["score"].idxmax()
    for i in (lo, hi):
        ax.annotate(f"{df['score'][i]:.1f}", (labels[i], df["score"][i]),
                    ha="center", va="bottom", fontsize=10, color=INK_2,
                    xytext=(0, 7), textcoords="offset points")

    fig.tight_layout()
    out = os.path.join(ASSETS, "weekday_scores.png")
    fig.savefig(out, dpi=150)
    print("wrote", out)


if __name__ == "__main__":
    os.makedirs(ASSETS, exist_ok=True)
    chart_three_signals()
    chart_weekday()
