"""Static figures for the README. Palette: validated default categorical slots 1-2."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from .analysis import ALPHA, CONTROL, ROUNDS_CAP, TREATMENT

ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "figures"

BLUE, ORANGE = "#2a78d6", "#eb6834"  # control, treatment (fixed by entity)
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
COLORS = {CONTROL: BLUE, TREATMENT: ORANGE}
LABELS = {CONTROL: "Gate at level 30 (control)", TREATMENT: "Gate at level 40 (test)"}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "font.size": 11, "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "legend.frameon": False,
})


def _save(fig, name: str) -> Path:
    FIG.mkdir(parents=True, exist_ok=True)
    p = FIG / name
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p


def retention_bars(m: dict) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    zc = stats.norm.ppf(1 - ALPHA / 2)
    x = np.arange(2)
    w = 0.36
    for i, arm in enumerate((CONTROL, TREATMENT)):
        key = "p_control" if arm == CONTROL else "p_treatment"
        vals, errs = [], []
        for met in ("retention_1", "retention_7"):
            t = m["tests"][met]
            n = m["checks"]["n_control" if arm == CONTROL else "n_treatment"]
            p = t[key]
            vals.append(p * 100)
            errs.append(zc * np.sqrt(p * (1 - p) / n) * 100)
        pos = x + (i - 0.5) * (w + 0.02)
        ax.bar(pos, vals, w, color=COLORS[arm], label=LABELS[arm], yerr=errs,
               error_kw={"ecolor": INK2, "elinewidth": 1.2, "capsize": 4}, zorder=3)
        for xp, v in zip(pos, vals):
            ax.text(xp, v + 1.6, f"{v:.1f}%", ha="center", va="bottom", fontsize=10, color=INK)
    ax.set_xticks(x, ["Day-1 retention", "Day-7 retention"])
    ax.set_ylabel("Share of players who returned (%)")
    ax.set_ylim(0, 55)
    ax.grid(axis="x", visible=False)
    d7 = m["tests"]["retention_7"]
    ax.set_title(f"Moving the gate to level 40 cost {abs(d7['diff_pp']):.2f} pp of day-7 retention")
    ax.legend(loc="upper right")
    ax.text(0, -0.16, "Error bars: 95% confidence interval per arm.", transform=ax.transAxes,
            fontsize=9, color=INK2)
    return _save(fig, "01_retention_by_arm.png")


def bootstrap_hist(m: dict, boots: dict) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for ax, met, title in zip(axes, ("retention_1", "retention_7"), ("Day-1", "Day-7")):
        b = boots[met]
        t = m["tests"][met]
        ax.hist(b, bins=60, color=ORANGE, alpha=0.85, edgecolor=SURFACE, linewidth=0.5, zorder=3)
        ax.axvline(0, color=INK, linewidth=1.5, zorder=4)
        ax.axvspan(t["boot_ci_low_pp"], t["boot_ci_high_pp"], color=GRID, alpha=0.6, zorder=1)
        ax.set_title(f"{title}: test is worse in {t['boot_share_treatment_worse']:.1%} of resamples",
                     fontsize=11)
        ax.set_xlabel("Retention difference, test - control (pp)")
        ax.grid(axis="y", visible=False)
        ax.text(0.02, 0.92, "no-difference line", transform=ax.get_xaxis_transform(),
                fontsize=9, color=INK2, ha="left")
    axes[0].set_ylabel("Bootstrap resamples")
    fig.suptitle("10,000 bootstrap resamples of the difference (shaded: 95% interval)",
                 x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.tight_layout()
    return _save(fig, "02_bootstrap_difference.png")


def rounds_ecdf(df: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    clean = df[df.sum_gamerounds <= ROUNDS_CAP]
    grid = np.arange(0, 201)
    for arm in (CONTROL, TREATMENT):
        r = np.sort(clean.loc[clean.version == arm, "sum_gamerounds"].to_numpy())
        share_ge = 1 - np.searchsorted(r, grid, side="left") / len(r)
        ax.plot(grid, share_ge * 100, color=COLORS[arm], linewidth=2, label=LABELS[arm])
    for lvl in (30, 40):
        ax.axvline(lvl, color=INK2, linewidth=0.8, linestyle="--")
        ax.text(lvl + 1, 92, f"{lvl}", color=INK2, fontsize=9)
    ax.set_xlabel("Game rounds played in the first 14 days")
    ax.set_ylabel("Players with at least this many rounds (%)")
    ax.set_ylim(0, 100)
    ax.set_title("The two arms play almost identically in the first 14 days")
    ax.legend(loc="upper right")
    return _save(fig, "03_rounds_survival.png")


def power_curve(m: dict) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    p = (m["tests"]["retention_7"]["p_control"] + m["tests"]["retention_7"]["p_treatment"]) / 2
    z = stats.norm.ppf(1 - ALPHA / 2) + stats.norm.ppf(0.8)
    n = np.linspace(2_000, 120_000, 400)
    mde = z * np.sqrt(p * (1 - p) * 2 / n) * 100
    ax.plot(n / 1000, mde, color=BLUE, linewidth=2, label="Smallest detectable D7 change (80% power)")
    obs = abs(m["tests"]["retention_7"]["diff_pp"])
    n_arm = (m["checks"]["n_control"] + m["checks"]["n_treatment"]) / 2
    ax.axhline(obs, color=ORANGE, linewidth=2, label=f"Observed D7 effect ({obs:.2f} pp)")
    ax.scatter([n_arm / 1000], [m["tests"]["retention_7"]["mde_pp_80power"]], s=60, color=INK,
               zorder=5, edgecolor=SURFACE, linewidth=2)
    ax.annotate(f"this test: ~{n_arm/1000:.0f}k players per arm\ncan detect {m['tests']['retention_7']['mde_pp_80power']:.2f} pp",
                (n_arm / 1000, m["tests"]["retention_7"]["mde_pp_80power"]), xytext=(55, 1.6),
                fontsize=9, color=INK2, arrowprops={"arrowstyle": "-", "color": INK2})
    ax.set_xlabel("Players per arm (thousands)")
    ax.set_ylabel("Absolute change in D7 retention (pp)")
    ax.set_ylim(0, 3)
    ax.set_title("The test was large enough - but only just - to see an effect this size")
    ax.legend(loc="upper right")
    return _save(fig, "04_power_curve.png")


def build_all(df: pd.DataFrame, metrics: dict, boots: dict) -> list[Path]:
    return [retention_bars(metrics), bootstrap_hist(metrics, boots), rounds_ecdf(df), power_curve(metrics)]
