"""Mark the two actual bonds after entry, using the Bank of England fitted curve.

Each gilt is priced off the Bank's zero-coupon spot curve (continuously compounded, linear in maturity),
and its yield is backed out. The bond's spread to that curve on the entry date (its rich/cheap) is held
constant, so the mark moves only with the curve. This is an estimate: a dealer or Bloomberg mark of the two
bonds is the exact figure.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from .bonds import Gilt


def settle_after(trade_day: date, lag: int = 1) -> date:
    d = trade_day
    for _ in range(lag):
        d += timedelta(days=1)
        while d.weekday() > 4:
            d += timedelta(days=1)
    return d


def curve_yield(b: Gilt, settle: date, row: pd.Series) -> float:
    """Yield at which the bond's own pricing matches its value off the spot curve."""
    ten, z = np.asarray(row.index, float), row.to_numpy(float) / 100
    flows = [(d, b.coupon / 2) for d in b.coupon_dates(settle)[1:]]
    flows[-1] = (flows[-1][0], flows[-1][1] + 100)
    if b.is_ex_div(settle):
        flows = flows[1:]
    pv = 0.0
    for d, cf in flows:
        t = (d - settle).days / 365.25
        pv += cf * np.exp(-np.interp(t, ten, z) * t)
    return brentq(lambda y: b.dirty_price(settle, y) - pv, -5.0, 30.0, xtol=1e-12)


def mark(snap: dict, curve: pd.DataFrame, long_m: float, short_m: float) -> dict:
    """Daily estimated yields, spread and P&L (GBP) of the position from entry to the last curve date."""
    s0, repo = snap["settle_date"], snap["repo"]
    entry_day = pd.Timestamp(snap["trade_date"])
    row0 = curve.loc[:entry_day].iloc[-1].dropna()
    legs = {"short_leg": -short_m * 1e6, "long_leg": long_m * 1e6}          # signed nominal
    basis = {k: snap[k]["yield"] - curve_yield(snap[k]["bond"], s0, row0) for k in legs}
    rows = []
    for day, row in curve.loc[entry_day:].iloc[1:].iterrows():
        st = settle_after(day.date())
        days = (st - s0).days
        rec = {"date": day}
        pnl = 0.0
        for k, nom in legs.items():
            g, b = snap[k], snap[k]["bond"]
            y = curve_yield(b, st, row.dropna()) + basis[k]
            p0, p1 = b.dirty_price(s0, g["yield"]), b.dirty_price(st, y)
            # a coupon belongs to us once its ex-dividend date has passed, even before it is paid
            coupons = sum(b.coupon / 2 for d in b.coupon_dates(s0)[1:]
                          if s0 <= Gilt.ex_div_date(d) < st)
            leg_pnl = nom / 100 * (p1 - p0 + coupons - p0 * repo * days / 365)
            rec[f"y_{k}"], rec[f"pnl_{k}"] = y, leg_pnl
            pnl += leg_pnl
        rec["spread_bp"] = (rec["y_long_leg"] - rec["y_short_leg"]) * 100
        rec["pnl_gbp"] = pnl
        rows.append(rec)
    path = pd.DataFrame(rows).set_index("date")
    entry_spread = (snap["long_leg"]["yield"] - snap["short_leg"]["yield"]) * 100
    return {"path": path, "basis_bp": {k: v * 100 for k, v in basis.items()}, "entry_spread": entry_spread,
            "worst_against_bp": max(0.0, (path["spread_bp"] - entry_spread).max()),
            "worst_pnl_gbp": min(0.0, path["pnl_gbp"].min())}
