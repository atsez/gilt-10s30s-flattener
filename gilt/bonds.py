"""Conventional gilt pricing from first principles.

UK Debt Management Office conventions:
- semi-annual coupons, actual/actual (ICMA) within each coupon period
- yield compounded semi-annually, discounting to the next coupon by the fraction r/s of a period,
  where r = days from settlement to the next coupon and s = days in the current coupon period
- the bond goes ex-dividend 7 business days before each coupon; a buyer settling in that window
  does not receive the next coupon and pays negative accrued interest

Risk conventions match Bloomberg YAS:
- DV01 (RISK_MID) = price change per 1bp, per 100 nominal, multiplied by 100
- convexity (CNVX_MID) = d2P/dy2 / P, divided by 100
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from scipy.optimize import brentq

EX_DIV_BUSINESS_DAYS = 7


@dataclass(frozen=True)
class Gilt:
    name: str
    coupon: float          # annual coupon, % of nominal
    maturity: date
    isin: str = ""

    # ---------------------------------------------------------------- schedule
    def coupon_dates(self, settle: date) -> list[date]:
        """[previous coupon, next coupon, ..., maturity] around a settlement date."""
        out, k = [], 0
        while True:
            d = self.maturity - relativedelta(months=6 * k)
            if self.maturity.day >= 28:                    # keep month-end coupons on month end
                d = d + relativedelta(day=self.maturity.day)
            out.append(d)
            if d <= settle:
                return out[::-1]
            k += 1

    @staticmethod
    def ex_div_date(coupon_date: date) -> date:
        """7 business days before the coupon (weekends skipped; UK bank holidays ignored)."""
        d, n = coupon_date, 0
        while n < EX_DIV_BUSINESS_DAYS:
            d -= timedelta(days=1)
            if d.weekday() < 5:
                n += 1
        return d

    # ---------------------------------------------------------------- pricing
    def _period(self, settle: date):
        ds = self.coupon_dates(settle)
        prev, nxt = ds[0], ds[1]
        return ds, prev, nxt, (nxt - prev).days, (nxt - settle).days

    def is_ex_div(self, settle: date) -> bool:
        _, _, nxt, _, _ = self._period(settle)
        return settle > self.ex_div_date(nxt)

    def accrued(self, settle: date) -> float:
        _, prev, nxt, s, r = self._period(settle)
        c = self.coupon / 2
        return -c * r / s if self.is_ex_div(settle) else c * (s - r) / s

    def dirty_price(self, settle: date, y: float) -> float:
        """Dirty price per 100 nominal at yield y (in %, semi-annual compounding)."""
        ds, _, _, s, r = self._period(settle)
        v, c, n = 1 / (1 + y / 200), self.coupon / 2, len(ds) - 1
        first = 1 if self.is_ex_div(settle) else 0          # ex-div: next coupon goes to the seller
        pv = sum(c * v ** (r / s + k) for k in range(first, n))
        return pv + 100 * v ** (r / s + n - 1)

    def clean_price(self, settle: date, y: float) -> float:
        return self.dirty_price(settle, y) - self.accrued(settle)

    def yield_from_clean(self, settle: date, clean: float) -> float:
        return brentq(lambda y: self.clean_price(settle, y) - clean, -5.0, 30.0, xtol=1e-12)

    # ---------------------------------------------------------------- risk
    def risk(self, settle: date, y: float, bump: float = 0.01) -> dict:
        """DV01, modified duration and convexity by central difference (bump in % yield)."""
        p = self.dirty_price(settle, y)
        up, dn = self.dirty_price(settle, y - bump), self.dirty_price(settle, y + bump)
        dv01 = (up - dn) / 2 / (bump * 100) * 100          # per 100 nominal, x100 (Bloomberg RISK)
        convexity = (up + dn - 2 * p) / (p * (bump / 100) ** 2)
        return {"dirty": p, "accrued": self.accrued(settle), "clean": p - self.accrued(settle),
                "dv01": dv01, "mod_duration": dv01 / p * 100, "convexity": convexity / 100}

    # ---------------------------------------------------------------- forward
    def forward_dirty(self, settle: date, y: float, repo: float, days: int) -> float:
        """Repo-forward dirty price: fund the bond at repo, credit any coupon received (reinvested at repo).

        repo is a decimal rate, act/365. This is the price at which holding the bond and carrying it
        breaks even, so comparing forward and spot yields gives carry in yield terms.
        """
        fwd = settle + timedelta(days=days)
        cash = self.dirty_price(settle, y) * (1 + repo * days / 365)
        for d in self.coupon_dates(settle)[1:]:
            if self.ex_div_date(d) >= fwd:
                break
            if settle <= self.ex_div_date(d):                # we own it on the record date
                cash -= self.coupon / 2 * (1 + repo * (fwd - d).days / 365)
        return cash

    def forward_yield(self, settle: date, y: float, repo: float, days: int) -> float:
        fwd = settle + timedelta(days=days)
        target = self.forward_dirty(settle, y, repo, days)
        return brentq(lambda z: self.dirty_price(fwd, z) - target, -5.0, 30.0, xtol=1e-12)
