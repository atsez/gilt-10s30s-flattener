"""The 10s30s flattener: long the 30-year gilt, short a DV01-matched amount of the 10-year.

Everything here is computed from the quoted yields and bond terms in data/snapshot_*.json.
Bloomberg's own risk figures are loaded only to check the pricer against them.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from .bonds import Gilt


def _d(s: str) -> date:
    return date.fromisoformat(s)


def load_snapshot(path: str) -> dict:
    with open(path) as f:
        snap = json.load(f)
    for leg in ("short_leg", "long_leg"):
        g = snap[leg]
        g["bond"] = Gilt(g["name"], g["coupon"], _d(g["maturity"]), g["isin"])
    snap["settle_date"] = _d(snap["settle"])
    return snap


# ------------------------------------------------------------------ 1. pricer vs Bloomberg
def reconcile(snap: dict) -> list[dict]:
    rows = []
    for leg in ("short_leg", "long_leg"):
        g = snap[leg]
        mine = g["bond"].risk(snap["settle_date"], g["yield"])
        for k in ("clean", "dirty", "accrued", "mod_duration", "dv01", "convexity"):
            rows.append({"bond": g["name"], "field": k, "bloomberg": g["yas"][k], "python": mine[k],
                         "diff": mine[k] - g["yas"][k]})
    return rows


# ------------------------------------------------------------------ 2. structure
def structure(snap: dict) -> dict:
    s, l, st = snap["short_leg"], snap["long_leg"], snap["settle_date"]
    rs, rl = s["bond"].risk(st, s["yield"]), l["bond"].risk(st, l["yield"])
    hedge = rl["dv01"] / rs["dv01"]                            # 10y nominal per 1 of 30y
    short_cx = rs["convexity"] * hedge
    return {"spread_bp": (l["yield"] - s["yield"]) * 100, "hedge_ratio": hedge,
            "risk_short": rs, "risk_long": rl, "short_convexity_weighted": short_cx,
            "net_convexity": rl["convexity"] - short_cx, "convexity_ratio": rl["convexity"] / short_cx}


# ------------------------------------------------------------------ 3. carry and roll
def carry_simple(snap: dict, st: dict) -> dict:
    """The spreadsheet method: coupon accrual less repo on the dirty price, plus roll x DV01."""
    H, repo = snap["horizon_days"], snap["repo"]
    legs = {}
    for leg, risk in (("short_leg", st["risk_short"]), ("long_leg", st["risk_long"])):
        g = snap[leg]
        coupon = g["coupon"] * H / 365
        funding = risk["dirty"] * repo * H / 365
        roll = snap["rolldown_bp"][leg] * risk["dv01"] / 100
        legs[leg] = {"coupon": coupon, "repo": funding, "roll": roll, "total": coupon - funding + roll}
    return _position(legs, st)


def carry_exact(snap: dict, st: dict) -> dict:
    """Cash-flow method: reprice each bond on the horizon date at its rolled-down yield, credit the
    actual coupon paid in the window (the 2035 pays on 22 Oct), and charge repo on the dirty price.
    """
    H, repo, s0 = snap["horizon_days"], snap["repo"], snap["settle_date"]
    fwd = s0 + timedelta(days=H)
    legs = {}
    for leg in ("short_leg", "long_leg"):
        g, b = snap[leg], snap[leg]["bond"]
        cost = b.dirty_price(s0, g["yield"]) * (1 + repo * H / 365)
        be = b.forward_dirty(s0, g["yield"], repo, H)          # breakeven dirty price on the horizon
        received = cost - be                                    # coupons in the window, with interest
        flat = b.dirty_price(fwd, g["yield"])                   # curve unchanged, no roll
        rolled = b.dirty_price(fwd, g["yield"] - snap["rolldown_bp"][leg] / 100)
        y_fwd = b.forward_yield(s0, g["yield"], repo, H)
        paid = sum(g["coupon"] / 2 for d in b.coupon_dates(s0)[1:] if s0 < d <= fwd)
        legs[leg] = {
            "accrual": b.accrued(fwd) - b.accrued(s0) + paid,               # coupon earned, act/act
            "pull_to_par": b.clean_price(fwd, g["yield"]) - b.clean_price(s0, g["yield"]),
            "repo": b.dirty_price(s0, g["yield"]) * repo * H / 365,
            "coupon_interest": received - paid,                               # repo saved once paid
            "carry": flat + received - cost, "roll": rolled - flat, "total": rolled + received - cost,
            "forward_yield": y_fwd, "carry_bp_yield": (y_fwd - g["yield"]) * 100}   # cheapening a long can absorb
    return _position(legs, st)


def carry_bridge(simple: dict, exact: dict, hedge: float) -> list[tuple[str, float]]:
    """GBP per quarter, per GBP1m of the 30y: how the spreadsheet carry becomes the exact carry."""
    def pos(f):  # long 30y less hedge x short 10y, per 100 nominal -> GBP per GBP1m
        return (f("long_leg") - hedge * f("short_leg")) * 1e4
    S, E = simple["legs"], exact["legs"]
    rows = [("Spreadsheet carry and roll", simple["gbp_per_quarter"]),
            ("Coupon accrual on actual/actual, not /365", pos(lambda k: E[k]["accrual"] - S[k]["coupon"])),
            ("Pull to par on discount bonds", pos(lambda k: E[k]["pull_to_par"])),
            ("Repo saved after the 2035 coupon is paid", pos(lambda k: E[k]["coupon_interest"])),
            ("Roll-down repriced exactly, not yield x DV01", pos(lambda k: E[k]["roll"] - S[k]["roll"]))]
    rows.append(("Exact carry and roll", exact["gbp_per_quarter"]))
    rows.append(("Unexplained", exact["gbp_per_quarter"] - sum(v for _, v in rows[:-1])))
    return rows


def _position(legs: dict, st: dict) -> dict:
    """GBP per quarter on GBP1m of the 30y against a DV01-matched short in the 10y."""
    gbp = legs["long_leg"]["total"] * 1e4 - st["hedge_ratio"] * legs["short_leg"]["total"] * 1e4
    dv01_gbp = st["risk_long"]["dv01"] * 100                    # GBP per bp per GBP1m of 30y
    return {"legs": legs, "gbp_per_quarter": gbp, "dv01_gbp": dv01_gbp, "bp_per_quarter": gbp / dv01_gbp}


# ------------------------------------------------------------------ 4. risk, scenarios, sizing
def risk_and_sizing(snap: dict, st: dict, carry: dict) -> dict:
    entry, stop = st["spread_bp"], snap["stop_bp"]
    scen = [{**s, "move_bp": entry - s["target_bp"]} for s in snap["scenarios"]]
    ev = sum(s["move_bp"] * s["prob"] for s in scen)
    gain_fwd, gain_mean = entry - snap["forward_spread_3m_bp"], entry - snap["ten_year_mean_bp"]
    loss = snap["nav_gbp_m"] * 1e6 * snap["risk_budget"]
    dv01 = loss / stop
    long_m = dv01 / (st["risk_long"]["dv01"] * 100)            # GBPm of the 30y
    short_m = long_m * st["hedge_ratio"]
    return {
        "stop_level_bp": entry + stop, "stop_in_3m_sd": stop / snap["spread_3m_sd_bp"],
        "above_ten_year_max_bp": entry + stop - snap["ten_year_max_bp"],
        "scenarios": scen, "ev_before_carry": ev, "ev_after_carry": ev + carry["bp_per_quarter"],
        "reward_risk_fwd": gain_fwd / stop, "reward_risk_mean": gain_mean / stop,
        "breakeven_p_fwd": stop / (stop + gain_fwd), "breakeven_p_mean": stop / (stop + gain_mean),
        "loss_at_stop": loss, "position_dv01": dv01, "long_m": long_m, "short_m": short_m,
        "gross_m": long_m + short_m, "carry_gbp_per_quarter": dv01 * carry["bp_per_quarter"],
    }


def cross_checks(snap: dict) -> dict:
    c, y10, y30 = snap["cross_checks"], snap["short_leg"]["yield"], snap["long_leg"]["yield"]
    gilt_curve = (y30 - y10) * 100
    swap_curve = (c["sonia_swap_30y"] - c["sonia_swap_10y"]) * 100
    infl = (c["breakeven_30y"] - c["breakeven_10y"]) * 100
    return {"gilt_10s30s": gilt_curve, "swap_10s30s": swap_curve, "gilt_specific": gilt_curve - swap_curve,
            "gilt_minus_swap_10y": (y10 - c["sonia_swap_10y"]) * 100, "gilt_minus_swap_30y": (y30 - c["sonia_swap_30y"]) * 100,
            "inflation_part": infl, "real_part": gilt_curve - infl}
