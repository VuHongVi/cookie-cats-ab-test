import numpy as np
import pandas as pd
import pytest
from scipy import stats

from cookie_cats import analysis as a


def test_two_proportion_matches_statsmodels_style_z():
    r = a.two_proportion(450, 1000, 400, 1000)
    pool = 0.425
    z = -0.05 / np.sqrt(pool * (1 - pool) * 2 / 1000)
    assert r["z"] == pytest.approx(z)
    assert r["p_value"] == pytest.approx(2 * stats.norm.sf(abs(z)))
    assert r["diff_pp"] == pytest.approx(-5.0)
    assert r["ci_low_pp"] < r["diff_pp"] < r["ci_high_pp"]


def test_bootstrap_centered_on_observed_difference():
    rng = np.random.default_rng(0)
    b = a.bootstrap_diff(450, 1000, 400, 1000, rng)
    assert b.mean() == pytest.approx(-5.0, abs=0.2)
    assert len(b) == a.N_BOOT


def test_holm_is_monotone_and_bounded():
    adj = a.holm({"x": 0.01, "y": 0.04, "z": 0.5})
    assert adj["x"] == pytest.approx(0.03)
    assert adj["y"] == pytest.approx(0.08)
    assert adj["z"] == pytest.approx(0.5)


def test_mde_shrinks_with_sample_size():
    assert a.mde_pp(0.2, 10_000, 10_000) > a.mde_pp(0.2, 40_000, 40_000)


def test_analyse_on_synthetic_data_detects_planted_effect():
    rng = np.random.default_rng(1)
    n = 20_000
    df = pd.DataFrame({
        "userid": np.arange(2 * n),
        "version": [a.CONTROL] * n + [a.TREATMENT] * n,
        "sum_gamerounds": rng.integers(0, 100, 2 * n),
        "retention_1": rng.random(2 * n) < 0.45,
        "retention_7": np.r_[rng.random(n) < 0.20, rng.random(n) < 0.17],
    })
    m, _ = a.analyse(df)
    assert m["checks"]["srm_p"] == pytest.approx(1.0)
    assert m["tests"]["retention_7"]["p_holm"] < 0.001
    assert m["decision"] == "keep_gate_30"


def test_real_data_contract():
    if not a.RAW.exists():
        pytest.skip("raw data not downloaded")
    df = a.load()
    assert df["userid"].is_unique
    assert set(df["version"]) == {a.CONTROL, a.TREATMENT}
    assert df.isna().sum().sum() == 0
