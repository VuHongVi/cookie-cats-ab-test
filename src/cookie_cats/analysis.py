"""Cookie Cats A/B test: gate at level 30 (control) vs level 40 (treatment).

Every number that appears in the README / report is produced here and written to
results/metrics.json. Nothing downstream is typed by hand.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "cookie_cats.csv"
RESULTS = ROOT / "results"

CONTROL, TREATMENT = "gate_30", "gate_40"
METRICS = ("retention_1", "retention_7")
ALPHA = 0.05
SEED = 20261127
N_BOOT = 10_000
# 14-day rounds above this are not plausible human play (> 1 round / 4 min, 24h a day, 14 days)
ROUNDS_CAP = 5_000


def load(path: Path = RAW) -> pd.DataFrame:
    df = pd.read_csv(path)
    expected = {"userid", "version", "sum_gamerounds", "retention_1", "retention_7"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"missing columns: {missing}")
    return df


def data_checks(df: pd.DataFrame) -> dict:
    counts = df["version"].value_counts()
    n_c, n_t = int(counts[CONTROL]), int(counts[TREATMENT])
    # sample ratio mismatch against the intended 50/50 split
    srm = stats.chisquare([n_c, n_t])
    outliers = df[df["sum_gamerounds"] > ROUNDS_CAP]
    return {
        "rows": int(len(df)),
        "unique_users": int(df["userid"].nunique()),
        "duplicate_users": int(len(df) - df["userid"].nunique()),
        "null_cells": int(df.isna().sum().sum()),
        "n_control": n_c,
        "n_treatment": n_t,
        "share_treatment": n_t / (n_c + n_t),
        "srm_chi2": float(srm.statistic),
        "srm_p": float(srm.pvalue),
        "rounds_outliers": int(len(outliers)),
        "rounds_outlier_max": int(outliers["sum_gamerounds"].max()) if len(outliers) else 0,
        "zero_round_share": float((df["sum_gamerounds"] == 0).mean()),
    }


def two_proportion(x_c: int, n_c: int, x_t: int, n_t: int) -> dict:
    """Wald CI on the difference (treatment - control) and pooled z-test."""
    p_c, p_t = x_c / n_c, x_t / n_t
    diff = p_t - p_c
    se_unpooled = np.sqrt(p_c * (1 - p_c) / n_c + p_t * (1 - p_t) / n_t)
    p_pool = (x_c + x_t) / (n_c + n_t)
    se_pooled = np.sqrt(p_pool * (1 - p_pool) * (1 / n_c + 1 / n_t))
    z = diff / se_pooled
    p = 2 * stats.norm.sf(abs(z))
    zc = stats.norm.ppf(1 - ALPHA / 2)
    return {
        "p_control": p_c,
        "p_treatment": p_t,
        "diff_pp": diff * 100,
        "ci_low_pp": (diff - zc * se_unpooled) * 100,
        "ci_high_pp": (diff + zc * se_unpooled) * 100,
        "rel_change": diff / p_c,
        "z": float(z),
        "p_value": float(p),
        "se_pp": se_unpooled * 100,
    }


def bootstrap_diff(x_c: int, n_c: int, x_t: int, n_t: int, rng: np.random.Generator) -> np.ndarray:
    """Non-parametric bootstrap of a difference in Bernoulli means.

    Resampling n users with replacement from a 0/1 column and taking the mean is
    exactly Binomial(n, p_hat) / n, so this is the classic bootstrap without
    materialising 10,000 x 90,000 resamples.
    """
    b_c = rng.binomial(n_c, x_c / n_c, N_BOOT) / n_c
    b_t = rng.binomial(n_t, x_t / n_t, N_BOOT) / n_t
    return (b_t - b_c) * 100


def bayes_prob_control_better(x_c, n_c, x_t, n_t, rng, draws: int = 200_000) -> float:
    a = rng.beta(1 + x_c, 1 + n_c - x_c, draws)
    b = rng.beta(1 + x_t, 1 + n_t - x_t, draws)
    return float((a > b).mean())


def mde_pp(p: float, n_c: int, n_t: int, power: float = 0.8) -> float:
    """Smallest absolute difference detectable at ALPHA (two-sided) with given power."""
    z = stats.norm.ppf(1 - ALPHA / 2) + stats.norm.ppf(power)
    return float(z * np.sqrt(p * (1 - p) * (1 / n_c + 1 / n_t)) * 100)


def holm(pvalues: dict[str, float]) -> dict[str, float]:
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m, running, out = len(items), 0.0, {}
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        out[k] = running
    return out


def analyse(df: pd.DataFrame) -> tuple[dict, dict]:
    rng = np.random.default_rng(SEED)
    checks = data_checks(df)
    g = df.groupby("version")
    n = g.size()
    n_c, n_t = int(n[CONTROL]), int(n[TREATMENT])

    tests, boots = {}, {}
    for m in METRICS:
        x = g[m].sum()
        x_c, x_t = int(x[CONTROL]), int(x[TREATMENT])
        t = two_proportion(x_c, n_c, x_t, n_t)
        b = bootstrap_diff(x_c, n_c, x_t, n_t, rng)
        t["boot_ci_low_pp"], t["boot_ci_high_pp"] = map(float, np.percentile(b, [2.5, 97.5]))
        t["boot_share_treatment_worse"] = float((b < 0).mean())
        t["bayes_prob_control_better"] = bayes_prob_control_better(x_c, n_c, x_t, n_t, rng)
        pooled = (x_c + x_t) / (n_c + n_t)
        t["mde_pp_80power"] = mde_pp(pooled, n_c, n_t)
        tests[m] = t
        boots[m] = b
    adj = holm({m: tests[m]["p_value"] for m in METRICS})
    for m in METRICS:
        tests[m]["p_holm"] = adj[m]

    # engagement: rounds in first 14 days, implausible outliers removed
    clean = df[df["sum_gamerounds"] <= ROUNDS_CAP]
    r_c = clean.loc[clean.version == CONTROL, "sum_gamerounds"]
    r_t = clean.loc[clean.version == TREATMENT, "sum_gamerounds"]
    mw = stats.mannwhitneyu(r_t, r_c, alternative="two-sided")
    rounds = {
        "mean_control": float(r_c.mean()),
        "mean_treatment": float(r_t.mean()),
        "median_control": float(r_c.median()),
        "median_treatment": float(r_t.median()),
        "mannwhitney_p": float(mw.pvalue),
        # P(random treatment player plays more rounds than random control player)
        "prob_superiority": float(mw.statistic / (len(r_t) * len(r_c))),
        "share_40plus_control": float((r_c >= 40).mean()),
        "share_40plus_treatment": float((r_t >= 40).mean()),
    }

    # D7 among players who came back on D1 (descriptive: conditions on a post-treatment outcome)
    d1 = df[df.retention_1]
    cond = d1.groupby("version")["retention_7"].mean()

    d7 = tests["retention_7"]
    per_100k = {
        "d7_players_lost": -d7["diff_pp"] * 1000,
        "d7_players_lost_low": -d7["ci_high_pp"] * 1000,
        "d7_players_lost_high": -d7["ci_low_pp"] * 1000,
    }

    metrics = {
        "checks": checks,
        "tests": tests,
        "rounds": rounds,
        "d7_given_d1": {"control": float(cond[CONTROL]), "treatment": float(cond[TREATMENT])},
        "impact_per_100k_installs": per_100k,
        "decision": "keep_gate_30" if (d7["p_holm"] < ALPHA and d7["diff_pp"] < 0) else "no_clear_winner",
        "params": {"alpha": ALPHA, "seed": SEED, "n_boot": N_BOOT, "rounds_cap": ROUNDS_CAP},
    }
    return metrics, boots


def _round(obj, nd=6):
    if isinstance(obj, dict):
        return {k: _round(v, nd) for k, v in obj.items()}
    if isinstance(obj, float):
        return round(obj, nd)
    return obj


def write_metrics(metrics: dict, path: Path | None = None) -> Path:
    path = path or RESULTS / "metrics.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_round(metrics), indent=2) + "\n", encoding="utf-8")
    return path
