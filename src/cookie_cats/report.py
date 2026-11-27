"""Render README.md from results/metrics.json so every number in it is generated."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _pct(x: float, nd: int = 1) -> str:
    return f"{x * 100:.{nd}f}%"


def _p(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def render(m: dict) -> list[Path]:
    c, t1, t7, r = m["checks"], m["tests"]["retention_1"], m["tests"]["retention_7"], m["rounds"]
    imp, cond = m["impact_per_100k_installs"], m["d7_given_d1"]
    srm_flag = c["srm_p"] < 0.01
    decision = (
        "**Keep the gate at level 30.** Moving it to level 40 lowers day-7 retention, the "
        "primary metric, and no metric moves the other way."
        if m["decision"] == "keep_gate_30"
        else "**No clear winner.** The primary metric did not move significantly."
    )
    srm_note = (
        "I would ask the engineering team how users were assigned before treating the size of the effect as final."
        if srm_flag else "The split is consistent with 50/50."
    )

    readme = f"""# Cookie Cats - A/B test of the first progression gate

Should the mobile puzzle game **Cookie Cats** put its first "gate" (where players must wait or pay
to continue) at **level 30** or **level 40**? This repo analyses the real experiment on
**{c['rows']:,} players** and turns it into a ship / don't-ship decision with its size and its risks.
Every number below is generated from [`results/metrics.json`](results/metrics.json) by
`python -m cookie_cats` - nothing is typed by hand.

## In 30 seconds

![Retention by arm](figures/01_retention_by_arm.png)

- **Decision:** {decision}
- **Primary metric, day-7 retention:** {_pct(t7['p_control'], 2)} (gate 30) vs {_pct(t7['p_treatment'], 2)} (gate 40),
  a change of **{t7['diff_pp']:+.2f} pp** ({t7['rel_change']:+.1%} relative), 95% CI [{t7['ci_low_pp']:+.2f}, {t7['ci_high_pp']:+.2f}] pp,
  p = {_p(t7['p_value'])} (Holm-adjusted {_p(t7['p_holm'])}). Bootstrap and Bayesian checks agree:
  gate 40 is worse in {t7['boot_share_treatment_worse']:.1%} of 10,000 resamples; P(gate 30 better) = {t7['bayes_prob_control_better']:.1%}.
- **What it is worth:** for every **100,000 installs**, gate 40 keeps about **{imp['d7_players_lost']:,.0f} fewer players
  on day 7** (95% CI {imp['d7_players_lost_low']:,.0f} to {imp['d7_players_lost_high']:,.0f}).
- **Secondary metrics:** day-1 retention {t1['diff_pp']:+.2f} pp (p = {_p(t1['p_value'])}, not significant on its own, same direction);
  rounds played in 14 days are flat (median {r['median_control']:.0f} vs {r['median_treatment']:.0f}).
- **Caveat worth raising:** the arms are not 50/50 ({c['n_control']:,} vs {c['n_treatment']:,}, sample-ratio-mismatch
  test p = {_p(c['srm_p'])}). {srm_note}

## Why the gate matters

A gate is a deliberate pause: the player waits, invites friends or pays to continue. The case for
moving it later is "let players get hooked first". The case for keeping it early is that a break
*earlier* keeps players from burning out on the game (hedonic adaptation). The experiment decides
between them.

## Data

| | |
|---|---|
| Source | Kaggle [`yufengsui/mobile-games-ab-testing`](https://www.kaggle.com/datasets/yufengsui/mobile-games-ab-testing) - one row per player who installed during the test |
| Columns | `userid`, `version` (gate_30 / gate_40), `sum_gamerounds` (rounds in the first 14 days), `retention_1`, `retention_7` (came back 1 / 7 days after install) |
| Rows | {c['rows']:,} players, {c['duplicate_users']} duplicate ids, {c['null_cells']} missing values |
| Arms | gate_30 (control) {c['n_control']:,} - gate_40 (test) {c['n_treatment']:,} |
| Outliers | {c['rounds_outliers']} player with {c['rounds_outlier_max']:,} rounds in 14 days (> {m['params']['rounds_cap']:,} is not human play); removed from the rounds analysis only |
| Never played | {_pct(c['zero_round_share'])} of installs played 0 rounds |

Raw data is not committed (`data/raw/` is git-ignored); see *Reproduce* below.

## Method

1. **Trust the experiment first.** Duplicate and missing-value checks, then a **sample-ratio-mismatch (SRM)**
   chi-square test on the arm sizes. A mismatch can mean users were dropped or assigned unevenly, which
   can bias every result after it.
2. **Primary metric fixed up front: day-7 retention.** It is closer to long-term value than day-1 and is
   what the gate is meant to protect. Day-1 retention and rounds played are secondary.
3. **Three independent views of the same difference** so the conclusion doesn't rest on one method:
   two-proportion z-test with a 95% Wald interval, a 10,000-resample bootstrap, and a Beta-Binomial
   posterior. Holm correction across the two retention metrics.
4. **Power check:** what is the smallest effect this sample could reliably detect? An effect below that
   line would be noise even if it looked large.
5. **Size it** in players per 100,000 installs, the unit a product team plans with. Revenue is not
   estimated: the data has no spend or purchase column.

## Results

| Metric | Gate 30 | Gate 40 | Difference (pp) | 95% CI (pp) | p | Holm p | Detectable at 80% power |
|---|---|---|---|---|---|---|---|
| Day-7 retention (primary) | {_pct(t7['p_control'], 2)} | {_pct(t7['p_treatment'], 2)} | {t7['diff_pp']:+.2f} | [{t7['ci_low_pp']:+.2f}, {t7['ci_high_pp']:+.2f}] | {_p(t7['p_value'])} | {_p(t7['p_holm'])} | {t7['mde_pp_80power']:.2f} pp |
| Day-1 retention | {_pct(t1['p_control'], 2)} | {_pct(t1['p_treatment'], 2)} | {t1['diff_pp']:+.2f} | [{t1['ci_low_pp']:+.2f}, {t1['ci_high_pp']:+.2f}] | {_p(t1['p_value'])} | {_p(t1['p_holm'])} | {t1['mde_pp_80power']:.2f} pp |

![Bootstrap distribution of the difference](figures/02_bootstrap_difference.png)

**Engagement does not explain the drop.** Rounds played in the first 14 days are almost identical
(mean {r['mean_control']:.1f} vs {r['mean_treatment']:.1f}; Mann-Whitney p = {_p(r['mannwhitney_p'])}; a random gate-40 player
out-plays a random gate-30 player {r['prob_superiority']:.1%} of the time), and {_pct(r['share_40plus_control'])} vs
{_pct(r['share_40plus_treatment'])} reach 40+ rounds. Players in both arms play about as much - gate-30 players are simply
more likely to *still be playing a week later*, which is what the early-break argument predicts.

![Rounds played](figures/03_rounds_survival.png)

Among players who came back on day 1, {_pct(cond['control'])} (gate 30) vs {_pct(cond['treatment'])} (gate 40) also came back
on day 7. This is descriptive only - it conditions on an outcome of the treatment - but it points the same way.

**The test had just enough power.** With ~{(c['n_control'] + c['n_treatment']) / 2000:.0f}k players per arm the smallest reliably detectable day-7
change is {t7['mde_pp_80power']:.2f} pp; the observed effect is {abs(t7['diff_pp']):.2f} pp. The day-1 effect ({abs(t1['diff_pp']):.2f} pp) is below
its detectable size ({t1['mde_pp_80power']:.2f} pp), so "not significant" there means "too small to see", not "no effect".

![Power curve](figures/04_power_curve.png)

## Recommendation

| | |
|---|---|
| **Ship** | Keep the gate at level 30. |
| **Why** | Day-7 retention {t7['diff_pp']:+.2f} pp with gate 40; holds across z-test, bootstrap, Bayesian and Holm correction. |
| **Worth** | ~{imp['d7_players_lost']:,.0f} day-7 players per 100,000 installs (CI {imp['d7_players_lost_low']:,.0f}-{imp['d7_players_lost_high']:,.0f}). |
| **Before closing** | Explain the SRM ({c['n_control']:,} vs {c['n_treatment']:,}, p = {_p(c['srm_p'])}): check assignment logging and whether any platform or country was dropped from one arm. |
| **Not measured** | Revenue: gate position may also change purchases at the gate. Add in-app spend per player as a guardrail in the next test. |
| **Next test** | Try the gate earlier still (e.g. level 25): if the early-break effect is real it may help further; guardrail day-1 retention. |

## Limitations

- **No timestamps**: novelty effects, weekday mix and test duration can't be checked.
- **Retention is a single-day flag** ("played on day 7"), not "played at any time after day 7".
- **`sum_gamerounds` counts rounds, not levels**, so "reached the gate" can't be measured directly.
- **SRM** as above: the direction of the result is consistent across every view, but its exact size
  depends on the assignment being clean.

## Reproduce

```powershell
pip install -r requirements.txt
pip install -e .
$env:KAGGLE_API_TOKEN = "<your token>"   # or ~/.kaggle/kaggle.json
kaggle datasets download -d yufengsui/mobile-games-ab-testing -p data/raw --unzip
python -m cookie_cats      # writes results/metrics.json, figures/, README.md
pytest -q
```

## Repo layout

```
src/cookie_cats/analysis.py   checks, tests, bootstrap, Bayesian, power, sizing -> results/metrics.json
src/cookie_cats/figures.py    the four charts in figures/
src/cookie_cats/report.py     renders this README from metrics.json
tests/                        unit tests on the statistics (known answers) and on the data contract
```
"""
    out = ROOT / "README.md"
    out.write_text(readme, encoding="utf-8")
    return [out]
