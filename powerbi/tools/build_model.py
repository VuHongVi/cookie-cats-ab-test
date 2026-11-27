"""Write the CookieCats semantic model as TMDL from the CSVs in powerbi/data.

    python powerbi/tools/build_model.py

Column types come from the CSVs; measures are listed below. Lineage tags are deterministic
(uuid5 of the object path) so re-running gives a clean diff. Auto date/time is off.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tmdl import write_model  # noqa: E402

MODEL = "CookieCats"
FORMATS = {  # column -> format string
    "p_control": "0.00%", "p_treatment": "0.00%", "rel_change": "+0.0%;-0.0%",
    "diff_pp": "+0.00;-0.00", "ci_low_pp": "+0.00;-0.00", "ci_high_pp": "+0.00;-0.00", "mde_pp_80power": "0.00",
    "p_value": "0.000", "p_holm": "0.000", "boot_share_treatment_worse": "0.0%", "bayes_prob_control_better": "0.0%",
    "bin_center_pp": "0.00", "share_at_least": "0%", "mde_pp": "0.00", "players_per_arm": "#,0",
    "sum_gamerounds": "#,0", "resamples": "#,0",
}
SORT_BY = {"arm_label": "arm_order", "metric_label": "metric_order"}
HIDDEN = {"arm_order", "metric_order", "check_order", "userid"}

P = "fact_players"
RET = "DIVIDE ( SWITCH ( SELECTEDVALUE ( fact_tests[metric] ), \"retention_1\", SUM ( fact_players[retention_1] ), \"retention_7\", SUM ( fact_players[retention_7] ) ), COUNTROWS ( fact_players ) )"
KPI = "CALCULATE ( MAX ( kpi_metrics[value] ), kpi_metrics[metric] = \"{}\" )"
T7 = "CALCULATE ( MAX ( fact_tests[{}] ), fact_tests[metric] = \"retention_7\" )"
MEASURES = [
    # (name, expression, format, folder, description)
    ("Players", f"COUNTROWS ( {P} )", "#,0", "Test", "Players randomised into the test."),
    ("D1 Retention", f"DIVIDE ( SUM ( {P}[retention_1] ), [Players] )", "0.00%", "Test", "Played again exactly 1 day after install."),
    ("D7 Retention", f"DIVIDE ( SUM ( {P}[retention_7] ), [Players] )", "0.00%", "Test", "Played again exactly 7 days after install."),
    ("D7 Retention Gate 30", f"CALCULATE ( [D7 Retention], {P}[version] = \"gate_30\" )", "0.00%", "Test", ""),
    ("D7 Retention Gate 40", f"CALCULATE ( [D7 Retention], {P}[version] = \"gate_40\" )", "0.00%", "Test", ""),
    ("D7 Difference pp", "( [D7 Retention Gate 40] - [D7 Retention Gate 30] ) * 100", "+0.00;-0.00", "Test", "Gate 40 minus gate 30, percentage points."),
    ("D7 CI Low pp", T7.format("ci_low_pp"), "+0.00;-0.00", "Test", "95% Wald interval, lower bound."),
    ("D7 CI High pp", T7.format("ci_high_pp"), "+0.00;-0.00", "Test", "95% Wald interval, upper bound."),
    ("D7 Holm p", T7.format("p_holm"), "0.000", "Test", "Holm-adjusted p across D1 and D7."),
    ("D7 Players Lost per 100k", "- [D7 Difference pp] * 1000", "#,0", "Impact", "Fewer day-7 players per 100,000 installs with gate 40."),
    ("Players Lost per 100k Low", KPI.format("players_lost_per_100k_low"), "#,0", "Impact", ""),
    ("Players Lost per 100k High", KPI.format("players_lost_per_100k_high"), "#,0", "Impact", ""),
    ("SRM p", KPI.format("srm_p"), "0.000", "Checks", "Chi-square test of the arm sizes against 50/50."),
    ("Gate 30 (control)", f"CALCULATE ( {RET}, {P}[version] = \"gate_30\" )", "0.00%", "Test", "Retention of the metric on the row, gate 30."),
    ("Gate 40 (test)", f"CALCULATE ( {RET}, {P}[version] = \"gate_40\" )", "0.00%", "Test", "Retention of the metric on the row, gate 40."),
    ("Bootstrap Resamples", "SUM ( fact_bootstrap_hist[resamples] )", "#,0", "Evidence", ""),
    ("In 95% Interval", "MAX ( fact_bootstrap_hist[in_ci] )", "0", "Evidence", "1 when the bin centre is inside the bootstrap 95% interval."),
    ("Share At Least", "SUM ( fact_rounds_survival[share_at_least] )", "0%", "Engagement", "Share of the arm with at least N rounds."),
    ("Smallest detectable change", "SUM ( fact_power_curve[mde_pp] )", "0.00", "Power", "80% power, two-sided alpha 0.05."),
    ("Observed D7 effect", "ABS ( [D7 Difference pp] )", "0.00", "Power", "Size of the observed day-7 change."),
]

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    write_model(root, MODEL, FORMATS, SORT_BY, HIDDEN, MEASURES)
