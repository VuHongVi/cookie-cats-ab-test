"""python -m cookie_cats.powerbi_export : write the CSV tables the Power BI model imports.

Uses the same analysis objects as results/metrics.json, so the report and the README agree.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .analysis import CONTROL, METRICS, ROUNDS_CAP, TREATMENT, analyse, load

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "powerbi" / "data"
ARM_LABEL = {CONTROL: "Gate 30 (control)", TREATMENT: "Gate 40 (test)"}
ARM_ORDER = {CONTROL: 1, TREATMENT: 2}
METRIC_LABEL = {"retention_1": "Day-1 retention", "retention_7": "Day-7 retention"}
METRIC_ORDER = {"retention_1": 1, "retention_7": 2}


def players(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "userid": df["userid"],
        "version": df["version"],
        "arm_label": df["version"].map(ARM_LABEL),
        "arm_order": df["version"].map(ARM_ORDER),
        "sum_gamerounds": df["sum_gamerounds"],
        "retention_1": df["retention_1"].astype(int),
        "retention_7": df["retention_7"].astype(int),
        "is_rounds_outlier": (df["sum_gamerounds"] > ROUNDS_CAP).astype(int),
    })


def tests(m: dict) -> pd.DataFrame:
    rows = []
    for k in METRICS:
        t = m["tests"][k]
        rows.append({"metric": k, "metric_label": METRIC_LABEL[k], "metric_order": METRIC_ORDER[k],
                     **{c: t[c] for c in ("p_control", "p_treatment", "diff_pp", "ci_low_pp", "ci_high_pp",
                                          "rel_change", "p_value", "p_holm", "boot_share_treatment_worse",
                                          "bayes_prob_control_better", "mde_pp_80power")}})
    return pd.DataFrame(rows)


def bootstrap_hist(m: dict, boots: dict, bins: int = 60) -> pd.DataFrame:
    rows = []
    for k in METRICS:
        counts, edges = np.histogram(boots[k], bins=bins)
        lo, hi = m["tests"][k]["boot_ci_low_pp"], m["tests"][k]["boot_ci_high_pp"]
        for c, a, b in zip(counts, edges[:-1], edges[1:]):
            center = (a + b) / 2
            rows.append({"metric": k, "bin_center_pp": round(center, 4), "resamples": int(c),
                         "in_ci": int(lo <= center <= hi)})
    return pd.DataFrame(rows)


def rounds_survival(df: pd.DataFrame) -> pd.DataFrame:
    clean = df[df["sum_gamerounds"] <= ROUNDS_CAP]
    grid = np.arange(0, 201)
    rows = []
    for arm in (CONTROL, TREATMENT):
        r = np.sort(clean.loc[clean.version == arm, "sum_gamerounds"].to_numpy())
        share = 1 - np.searchsorted(r, grid, side="left") / len(r)
        rows += [{"arm_label": ARM_LABEL[arm], "arm_order": ARM_ORDER[arm], "rounds": int(g), "share_at_least": float(s)}
                 for g, s in zip(grid, share)]
    return pd.DataFrame(rows)


def power_curve(m: dict) -> pd.DataFrame:
    from scipy import stats
    t7 = m["tests"]["retention_7"]
    p = (t7["p_control"] + t7["p_treatment"]) / 2
    z = stats.norm.ppf(1 - m["params"]["alpha"] / 2) + stats.norm.ppf(0.8)
    n = np.arange(2_000, 120_001, 1_000)
    return pd.DataFrame({"players_per_arm": n, "mde_pp": z * np.sqrt(p * (1 - p) * 2 / n) * 100})


def checks(m: dict) -> pd.DataFrame:
    c = m["checks"]
    rows = [
        ("Rows / unique players", f"{c['rows']:,} / {c['unique_users']:,}", "PASS"),
        ("Duplicate player ids", f"{c['duplicate_users']}", "PASS" if c["duplicate_users"] == 0 else "FAIL"),
        ("Missing values", f"{c['null_cells']}", "PASS" if c["null_cells"] == 0 else "FAIL"),
        ("Arm sizes (gate 30 / gate 40)", f"{c['n_control']:,} / {c['n_treatment']:,}", "INFO"),
        ("Sample ratio mismatch, chi-square p", f"{c['srm_p']:.3f}",
         "FLAG - check assignment" if c["srm_p"] < 0.01 else "PASS"),
        (f"Players with more than {m['params']['rounds_cap']:,} rounds", f"{c['rounds_outliers']} (max {c['rounds_outlier_max']:,})",
         "Removed from rounds analysis"),
        ("Players with 0 rounds", f"{c['zero_round_share']:.1%}", "INFO - kept"),
    ]
    return pd.DataFrame([{"check_order": i + 1, "check": a, "value_text": b, "verdict": v} for i, (a, b, v) in enumerate(rows)])


def kpis(m: dict) -> pd.DataFrame:
    c, imp = m["checks"], m["impact_per_100k_installs"]
    vals = {
        "srm_p": c["srm_p"], "srm_chi2": c["srm_chi2"],
        "players_lost_per_100k_low": imp["d7_players_lost_low"], "players_lost_per_100k_high": imp["d7_players_lost_high"],
        "rounds_outlier_max": c["rounds_outlier_max"], "zero_round_share": c["zero_round_share"],
    }
    return pd.DataFrame({"metric": list(vals), "value": list(vals.values())})


def reconciliation(m: dict) -> str:
    """DAX query comparing model measures with results/metrics.json (run against the open model)."""
    t1, t7, c, imp = m["tests"]["retention_1"], m["tests"]["retention_7"], m["checks"], m["impact_per_100k_installs"]
    checks = [
        ("[Players]", c["rows"], 0),
        ("[D1 Retention]", (t1["p_control"] * c["n_control"] + t1["p_treatment"] * c["n_treatment"]) / c["rows"], 1e-9),
        ("[D7 Retention Gate 30]", t7["p_control"], 1e-9),
        ("[D7 Retention Gate 40]", t7["p_treatment"], 1e-9),
        ("[D7 Difference pp]", t7["diff_pp"], 1e-6),
        ("[D7 CI Low pp]", t7["ci_low_pp"], 1e-6),
        ("[D7 CI High pp]", t7["ci_high_pp"], 1e-6),
        ("[D7 Holm p]", t7["p_holm"], 1e-6),
        ("[D7 Players Lost per 100k]", imp["d7_players_lost"], 1e-3),
        ("[SRM p]", c["srm_p"], 1e-6),
        ("CALCULATE ( [Gate 30 (control)], fact_tests[metric] = \"retention_1\" )", t1["p_control"], 1e-9),
        ("CALCULATE ( [Gate 40 (test)], fact_tests[metric] = \"retention_1\" )", t1["p_treatment"], 1e-9),
        ("CALCULATE ( [Bootstrap Resamples], fact_bootstrap_hist[metric] = \"retention_7\" )", m["params"]["n_boot"], 0),
    ]
    rows = ",\n".join(
        f'ROW ( "check_id", {i}, "measure", "{e.replace(chr(34), chr(39))}", "expected", {float(v)!r}, "actual", {e}, "tol", {tol:.12f} )'
        for i, (e, v, tol) in enumerate(checks, 1))
    return ("// Generated by python -m cookie_cats.powerbi_export from results/metrics.json.\n"
            "// Run against the open CookieCats model; every row must say PASS.\n"
            f"EVALUATE\nVAR t = UNION (\n{rows}\n)\n"
            "RETURN ADDCOLUMNS ( t, \"result\", IF ( ABS ( [actual] - [expected] ) <= [tol], \"PASS\", \"FAIL\" ) )\n"
            "ORDER BY [check_id]\n")


def main() -> None:
    df = load()
    m, boots = analyse(df)
    OUT.mkdir(parents=True, exist_ok=True)
    tables = {
        "fact_players": players(df), "fact_tests": tests(m), "fact_bootstrap_hist": bootstrap_hist(m, boots),
        "fact_rounds_survival": rounds_survival(df), "fact_power_curve": power_curve(m),
        "fact_checks": checks(m), "kpi_metrics": kpis(m),
    }
    for name, t in tables.items():
        t.to_csv(OUT / f"{name}.csv", index=False, float_format="%.10g")
        print(f"{name:22s} {len(t):>7,} rows")
    dax = ROOT / "powerbi" / "tools" / "reconciliation_query.dax"
    dax.write_text(reconciliation(m), encoding="utf-8")
    print("reconciliation ->", dax.relative_to(ROOT))


if __name__ == "__main__":
    main()
