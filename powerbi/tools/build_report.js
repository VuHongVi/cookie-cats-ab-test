#!/usr/bin/env node
// Generates the Cookie Cats Power BI report pages (PBIR) from the approved spec in _brief/report-spec.md.
// Usage: node powerbi/tools/build_report.js powerbi/CookieCats.Report
// Numbers in charts/cards come from model measures/columns; sentences match README.md (results/metrics.json).
'use strict';
const path = require('path');
const L = require('./pbir_lib');
const { C, M, hid, str, num, int, bool, color, measure, column, rect, slot, chrome, container, run, textbox, accent, insight,
  kpiCard, axisFont, gridY, tableObjects, flagColor, slicer, catFilter } = L;

const REPORT = path.resolve(process.argv[2] || path.join(__dirname, '..', 'CookieCats.Report'));
const { pages, page } = L.createReport(4);
const named = (p, displayName) => ({ ...p, displayName });
const legendTop = [{ properties: { show: bool(true), position: str('Top'), fontSize: num(11), labelColor: color(C.muted) } }];
const fillFor = (name, hex) => ({ properties: { fill: color(hex) }, selector: { metadata: `${M}.${name}` } });

// 1. Decision -----------------------------------------------------------------
page('decision', 'Decision', 'Decision', 'Keep the gate at level 30: moving it to level 40 costs day-7 players', () => {
  const strip = rect([1, 2, 13, 4]);
  const cards = [
    ['Players in the test', 'Players', 'Players randomised into the two arms.'],
    ['Day-7 retention, gate 30', 'D7 Retention Gate 30', 'Control: played again 7 days after install.'],
    ['Day-7 retention, gate 40', 'D7 Retention Gate 40', 'Test: played again 7 days after install.'],
    ['Day-7 change (pp)', 'D7 Difference pp', 'Gate 40 minus gate 30; 95% CI -1.33 to -0.31.'],
    ['Players lost per 100k', 'D7 Players Lost per 100k', 'Fewer day-7 players per 100,000 installs with gate 40.'],
    ['Arm-split check (SRM p)', 'SRM p', 'Below 0.01: check how players were assigned.'],
  ];
  const panel = rect([8, 4, 13, 13]);
  const para = (label, text) => [
    { textRuns: [run(label, 11, { font: 'Segoe UI Semibold', col: C.orange })] },
    { textRuns: [run(text, 14)] },
    { textRuns: [run(' ', 6)] },
  ];
  return [
    ...cards.map((c, i) => kpiCard('decision:k:' + i, slot(strip, i, 6), ...c, 30)),
    container(hid('decision:chart'), rect([1, 4, 8, 11]), {
      visualType: 'clusteredColumnChart',
      query: { queryState: { Category: { projections: [column('fact_tests', 'metric_label')] }, Y: { projections: [measure('Gate 30 (control)'), measure('Gate 40 (test)')] } },
        sortDefinition: { sort: [{ field: column('fact_tests', 'metric_label').field, direction: 'Ascending' }], isDefaultSort: false } },
      objects: {
        categoryAxis: [{ properties: { ...axisFont, fontSize: num(12), showAxisTitle: bool(false) } }],
        valueAxis: [{ properties: { ...axisFont, ...gridY, showAxisTitle: bool(false), start: num(0), end: num(0.5) } }],
        dataPoint: [fillFor('Gate 30 (control)', C.blue), fillFor('Gate 40 (test)', C.orange)],
        labels: [{ properties: { show: bool(true), fontSize: num(13), color: color(C.text), labelDisplayUnits: num(1) } }],
        legend: legendTop,
      },
      visualContainerObjects: chrome({ title: 'Day-1 and day-7 retention by arm', subtitle: 'Share of players who played again exactly 1 / 7 days after install. Blue = gate 30 (control), orange = gate 40 (test).', alt: 'Clustered columns of day-1 and day-7 retention for gate 30 and gate 40.' }),
    }),
    ...insight('decision:i1', rect([1, 11, 8, 13]), 'Day-7 retention is 19.02% with the gate at 30 and 18.20% at 40: -0.82 pp (95% CI -1.33 to -0.31, Holm p = 0.003). Day-1 moves the same way (-0.59 pp) but within noise.', 'fact_players.csv, fact_tests.csv (results/metrics.json)'),
    accent(hid('decision:panel:bar'), { ...panel, width: 8 }, C.orange),
    textbox(hid('decision:panel'), { ...panel, x: panel.x + 8, width: panel.width - 8 }, [
      { textRuns: [run('Recommendation', 18, { font: 'Segoe UI Semibold' })] },
      { textRuns: [run(' ', 8)] },
      ...para('SHIP', 'Keep the gate at level 30.'),
      ...para('WHY', 'Day-7 retention, the primary metric, drops with gate 40. z-test, bootstrap (gate 40 worse in 99.9% of resamples) and Bayesian (P = 99.9%) agree.'),
      ...para('WORTH', 'About 820 day-7 players per 100,000 installs (95% CI 312 to 1,328).'),
      ...para('BEFORE CLOSING', 'Explain the uneven split: 44,700 vs 45,489 players (p = 0.009). Check assignment logging.'),
      ...para('NOT MEASURED', 'Revenue. Add spend per player as a guardrail in the next test.'),
      ...para('NEXT TEST', 'An earlier gate (level 25), guardrail day-1 retention.'),
      { textRuns: [run('Source: README Recommendation (results/metrics.json)', 10, { col: C.muted, italic: true })] },
    ], { bg: C.orangeTint, alt: 'Recommendation: keep the gate at level 30.' }),
  ];
});

// 2. Evidence -----------------------------------------------------------------
page('evidence', 'Evidence', 'Evidence', 'Three statistical views agree: gate 40 lowers day-7 retention', () => {
  const T = 'fact_tests';
  const cols = [
    ['metric_label', 'Metric'], ['p_control', 'Gate 30'], ['p_treatment', 'Gate 40'], ['diff_pp', 'Change (pp)'],
    ['ci_low_pp', 'CI low (pp)'], ['ci_high_pp', 'CI high (pp)'], ['p_value', 'p'], ['p_holm', 'Holm p'],
    ['boot_share_treatment_worse', 'Bootstrap: gate 40 worse'], ['bayes_prob_control_better', 'Bayes: P(gate 30 better)'],
    ['mde_pp_80power', 'Detectable at 80% power (pp)'],
  ];
  const hist = (key, r, metric, title, subtitle, alt) => container(hid(key), r, {
    visualType: 'clusteredColumnChart',
    query: { queryState: { Category: { projections: [column('fact_bootstrap_hist', 'bin_center_pp')] }, Y: { projections: [measure('Bootstrap Resamples')] } } },
    objects: {
      categoryAxis: [{ properties: { ...axisFont, axisType: str('Scalar'), showAxisTitle: bool(true), titleText: str('Gate 40 minus gate 30 (pp)') } }],
      valueAxis: [{ properties: { ...axisFont, ...gridY, showAxisTitle: bool(false) } }],
      dataPoint: [{ properties: { defaultColor: color(C.orange) } }, flagColor('fact_bootstrap_hist', 'in_ci', C.orange, '#F5C4AF')],
      legend: [{ properties: { show: bool(false) } }],
    },
    visualContainerObjects: chrome({ title, subtitle, alt }),
  }, { filterConfig: { filters: [catFilter(key + ':metric', 'fact_bootstrap_hist', 'metric', `'${metric}'`)] } });
  return [
    container(hid('evidence:table'), rect([1, 2, 13, 5]), {
      visualType: 'tableEx',
      query: { queryState: { Values: { projections: cols.map(([c, n]) => named(column(T, c), n)) } },
        sortDefinition: { sort: [{ field: column(T, 'metric_label').field, direction: 'Descending' }], isDefaultSort: false } },
      objects: tableObjects(14),
      visualContainerObjects: chrome({ title: 'Test results by metric', subtitle: 'Change = gate 40 minus gate 30. Holm p corrects for testing two metrics. Detectable = smallest change this sample finds 80% of the time.', alt: 'Table of test results for day-1 and day-7 retention.' }),
    }),
    hist('evidence:d7', rect([1, 5, 7, 11]), 'retention_7', 'Day-7: bootstrap distribution of the change', '10,000 resamples of players with replacement. Dark bars = inside the 95% interval; it ends below zero.', 'Histogram of bootstrapped day-7 differences, all below zero.'),
    hist('evidence:d1', rect([7, 5, 13, 11]), 'retention_1', 'Day-1: bootstrap distribution of the change', 'Same method. The 95% interval reaches above zero.', 'Histogram of bootstrapped day-1 differences, interval crosses zero.'),
    ...insight('evidence:i1', rect([1, 11, 13, 13]), 'Day-7: gate 40 is worse in 99.9% of resamples and the 95% interval (-1.33 to -0.30 pp) excludes zero. Day-1: worse in 96.2% of resamples but the interval (-1.24 to +0.06 pp) crosses zero, so it is a supporting signal, not a finding.', 'fact_bootstrap_hist.csv, fact_tests.csv'),
  ];
});

// 3. Engagement and power -------------------------------------------------------
page('power', 'Engagement and power', 'Engagement and power', 'Play is unchanged; the test was just big enough', () => [
  slicer('power:slicer', { ...rect([7, 1, 9, 2]), y: rect([7, 1, 9, 2]).y - 8, height: 80 }, 'fact_rounds_survival', 'arm_label', 'Arm (rounds chart)'),
  container(hid('power:rounds'), rect([1, 2, 7, 11]), {
    visualType: 'lineChart',
    query: { queryState: { Category: { projections: [column('fact_rounds_survival', 'rounds')] }, Y: { projections: [measure('Share At Least')] }, Series: { projections: [column('fact_rounds_survival', 'arm_label')] } } },
    objects: {
      categoryAxis: [{ properties: { ...axisFont, axisType: str('Scalar'), showAxisTitle: bool(true), titleText: str('Game rounds in the first 14 days') } }],
      valueAxis: [{ properties: { ...axisFont, ...gridY, showAxisTitle: bool(false), start: num(0), end: num(1) } }],
      lineStyles: [{ properties: { strokeWidth: num(2), showMarker: bool(false) } }],
      legend: legendTop,
    },
    visualContainerObjects: chrome({ title: 'Players with at least N rounds in the first 14 days', subtitle: 'Share of each arm that played N or more game rounds (one player with 49,854 rounds removed). Blue = gate 30, orange = gate 40.', alt: 'Two almost identical decay curves of rounds played by arm.' }),
  }),
  ...insight('power:i1', rect([1, 11, 7, 13]), 'The curves overlap: median 17 vs 16 rounds, and 30.3% vs 30.4% reach 40+ rounds (Mann-Whitney p = 0.051). Gate-30 players do not play more; they are more likely to still be playing a week later.', 'fact_rounds_survival.csv, results/metrics.json'),
  container(hid('power:curve'), rect([7, 2, 13, 11]), {
    visualType: 'lineChart',
    query: { queryState: { Category: { projections: [column('fact_power_curve', 'players_per_arm')] }, Y: { projections: [measure('Smallest detectable change'), measure('Observed D7 effect')] } } },
    objects: {
      categoryAxis: [{ properties: { ...axisFont, axisType: str('Scalar'), showAxisTitle: bool(true), titleText: str('Players per arm') } }],
      valueAxis: [{ properties: { ...axisFont, ...gridY, showAxisTitle: bool(true), titleText: str('Change in day-7 retention (pp)'), start: num(0), end: num(3) } }],
      dataPoint: [fillFor('Smallest detectable change', C.blue), fillFor('Observed D7 effect', C.orange)],
      lineStyles: [
        { properties: { strokeWidth: num(3), showMarker: bool(false) } },
        { properties: { strokeWidth: num(2), lineStyle: str('dashed'), showMarker: bool(false) }, selector: { metadata: `${M}.Observed D7 effect` } },
      ],
      legend: legendTop,
    },
    visualContainerObjects: chrome({ title: 'Smallest detectable day-7 change by sample size', subtitle: 'Two-sided alpha 0.05, 80% power, baseline day-7 retention about 18.6%. Dashed orange = the effect this test observed.', alt: 'Power curve falling below the observed effect at about 35,000 players per arm.' }),
  }),
  ...insight('power:i2', rect([7, 11, 13, 13]), 'With about 45k players per arm the test detects 0.73 pp; the observed 0.82 pp is just above that. The day-1 change (0.59 pp) is below its detectable size (0.93 pp): not significant there means too small to see.', 'fact_power_curve.csv, fact_tests.csv'),
], { headerCols: 7 });

// 4. Data checks and limitations -------------------------------------------------
page('checks', 'Data checks and limitations', 'Data checks and limitations', 'What to check before the result is final', () => {
  const T = 'fact_checks';
  const lim = rect([7, 2, 13, 13]);
  const items = [
    'Arms are not 50/50: 44,700 vs 45,489 (chi-square p = 0.009). Check assignment logging before treating the size as final.',
    'No timestamps: novelty effects, weekday mix and test length cannot be checked.',
    "Retention is a single-day flag (played on day 7), not 'played any time after day 7'.",
    "sum_gamerounds counts rounds, not levels, so 'reached the gate' cannot be measured.",
    'One player with 49,854 rounds in 14 days is removed from the rounds analysis only.',
    'No revenue column: the decision is about retention, not money.',
  ];
  return [
    container(hid('checks:table'), rect([1, 2, 7, 13]), {
      visualType: 'tableEx',
      query: { queryState: { Values: { projections: [named(column(T, 'check_order'), '#'), named(column(T, 'check'), 'Check'), named(column(T, 'value_text'), 'Result'), named(column(T, 'verdict'), 'Verdict')] } },
        sortDefinition: { sort: [{ field: column(T, 'check_order').field, direction: 'Ascending' }], isDefaultSort: false } },
      objects: tableObjects(14),
      visualContainerObjects: chrome({ title: 'Data checks', subtitle: 'Run on the raw file before any test.', alt: 'Table of seven data checks with results.' }),
    }),
    accent(hid('checks:bar'), { ...lim, width: 8 }, C.orange),
    textbox(hid('checks:text'), { ...lim, x: lim.x + 8, width: lim.width - 8 }, [
      { textRuns: [run('Limitations', 18, { font: 'Segoe UI Semibold' })] },
      ...items.flatMap((t) => [{ textRuns: [run(' ', 8)] }, { textRuns: [run(t, 16)], listType: 'bullet', indent: 1 }]),
      { textRuns: [run(' ', 8)] },
      { textRuns: [run('Source: README Limitations; data: Kaggle yufengsui/mobile-games-ab-testing', 10, { col: C.muted, italic: true })] },
    ], { bg: C.card, alt: 'Limitations of the Cookie Cats data' }),
  ];
});

L.writeReport(REPORT, pages);
