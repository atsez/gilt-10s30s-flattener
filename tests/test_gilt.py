"""Pricer against Bloomberg, the trade against the spreadsheet, and the history tools on synthetic data."""
import os
import sys
from datetime import date

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from gilt import history as H          # noqa: E402
from gilt import trade as T            # noqa: E402
from gilt.bonds import Gilt            # noqa: E402
from gilt.curve import fit_nss, nss    # noqa: E402

SNAP = T.load_snapshot(os.path.join(ROOT, "data", "snapshot_20260814.json"))
G35 = SNAP["short_leg"]["bond"]


# ------------------------------------------------------------------ pricer
def test_pricer_matches_bloomberg_yas():
    for r in T.reconcile(SNAP):
        assert abs(r["diff"]) < 1e-5, r


def test_price_yield_round_trip():
    st = SNAP["settle_date"]
    for y in (0.5, 4.0, 5.019935, 9.0):
        assert G35.yield_from_clean(st, G35.clean_price(st, y)) == pytest.approx(y, abs=1e-9)


def test_month_end_coupons_stay_on_month_end():
    g = Gilt("2056", 5.375, date(2056, 1, 31))
    assert g.coupon_dates(date(2026, 8, 17))[:3] == [date(2026, 7, 31), date(2027, 1, 31), date(2027, 7, 31)]


def test_ex_dividend_buyer_loses_the_coupon():
    # 22 Oct 2026 coupon: ex-dividend 13 Oct. Settling on the 14th, accrued turns negative and the
    # dirty price drops by about the coupon against settling on the 12th.
    before, after = date(2026, 10, 12), date(2026, 10, 14)
    assert G35.accrued(before) > 0 > G35.accrued(after)
    drop = G35.dirty_price(before, 5.0) - G35.dirty_price(after, 5.0)
    assert drop == pytest.approx(4.75 / 2, abs=0.05)


# ------------------------------------------------------------------ trade vs the Excel model
def test_spreadsheet_figures_reproduced():
    st = T.structure(SNAP)
    simple = T.carry_simple(SNAP, st)
    r = T.risk_and_sizing(SNAP, st, simple)
    assert st["hedge_ratio"] == pytest.approx(1.8738, abs=1e-4)
    assert st["convexity_ratio"] == pytest.approx(2.59, abs=0.005)
    assert simple["gbp_per_quarter"] == pytest.approx(-2351, abs=1)
    assert simple["bp_per_quarter"] == pytest.approx(-1.74, abs=0.005)
    assert (r["long_m"], r["short_m"]) == (pytest.approx(18.53, abs=0.005), pytest.approx(34.73, abs=0.005))
    assert (r["ev_before_carry"], r["ev_after_carry"]) == (pytest.approx(1.88, abs=0.005), pytest.approx(0.14, abs=0.005))


def test_carry_bridge_closes():
    st = T.structure(SNAP)
    rows = dict(T.carry_bridge(T.carry_simple(SNAP, st), T.carry_exact(SNAP, st), st["hedge_ratio"]))
    assert abs(rows["Unexplained"]) < 1e-6


# ------------------------------------------------------------------ curve
def test_nss_recovers_a_known_curve():
    t = np.array([0.5, 1, 2, 3, 5, 7, 10, 15, 20, 25, 30, 40])
    true = [4.5, -0.8, 1.5, -2.0, 1.8, 15.0]
    fit = fit_nss(t, nss(t, true))
    assert fit["max_err_bp"] < 0.1


# ------------------------------------------------------------------ history tools
def _ar1(phi, n=2000, seed=0):
    rng, x = np.random.default_rng(seed), np.zeros(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + rng.normal()
    return pd.Series(x, index=pd.bdate_range("2016-01-01", periods=n))


def test_stationarity_separates_reverting_from_random_walk():
    rev, rw = H.stationarity(_ar1(0.9)), H.stationarity(_ar1(1.0, seed=1))
    assert rev["adf_p"] < 0.01 and rev["half_life_days"] == pytest.approx(np.log(2) / -np.log(0.9), rel=0.25)
    assert rw["adf_p"] > 0.05


def test_rule_backtest_has_no_lookahead():
    s = _ar1(0.98, seed=2) * 5 + 50
    first = H.rule_backtest(s).iloc[0]
    t = s.index.get_loc(first.entry_date)                    # changing anything after entry...
    s2 = s.copy()
    s2.iloc[t + 1:] += 40
    assert H.rule_backtest(s2).iloc[0].entry_date == first.entry_date   # ...cannot move the entry


def test_base_rates_count_only_complete_quarters():
    s = _ar1(0.95, n=600, seed=3)
    fc = H.forward_change(s, 91)
    assert fc.index[-1] + pd.Timedelta(days=91) <= s.index[-1]
    assert H.base_rates(s, levels=(None,)).iloc[0].obs == len(fc)


def test_mark_has_no_jump_through_the_ex_dividend_window():
    # flat 5% curve across the 2035's ex-dividend date (13 Oct) and payment (22 Oct): P&L must move smoothly
    from gilt import mark as M
    days = pd.bdate_range("2026-08-14", "2026-11-12")
    curve = pd.DataFrame(5.0, index=days, columns=[0.5 * k for k in range(1, 81)])
    p = M.mark(SNAP, curve, 18.53, 34.73)["path"]
    assert p.pnl_gbp.diff().abs().max() < 20_000
