"""Nelson-Siegel-Svensson curve fit and roll-down.

    y(t) = b0 + b1 * L(t/l1) + b2 * C(t/l1) + b3 * C(t/l2)
    L(x) = (1 - e^-x) / x          slope loading, 1 at the short end, 0 at the long end
    C(x) = L(x) - e^-x             hump loading, 0 at both ends

b0 is the long-run level, b1 the short-minus-long slope, b2 and b3 two humps at decay lengths l1 and l2.
The second hump is what lets the curve peak near 30 years and invert beyond it, as the gilt curve does.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares


def _load(t, lam):
    x = np.asarray(t, float) / lam
    L = (1 - np.exp(-x)) / x
    return L, L - np.exp(-x)


def nss(t, p) -> np.ndarray:
    b0, b1, b2, b3, l1, l2 = p
    L1, C1 = _load(t, l1)
    _, C2 = _load(t, l2)
    return b0 + b1 * L1 + b2 * C1 + b3 * C2


def fit_nss(tenors, yields) -> dict:
    """Least-squares fit. The decay lengths are searched on a grid, then everything is refined jointly,
    because NSS has local minima and a single start often lands in one."""
    t, y = np.asarray(tenors, float), np.asarray(yields, float)
    best = None
    for l1 in (0.5, 1, 2, 3, 5):
        for l2 in (5, 8, 12, 20, 30):
            if l2 <= l1:
                continue
            p0 = [y[-1], y[0] - y[-1], 0.0, 0.0, l1, l2]
            r = least_squares(lambda p: nss(t, p) - y, p0,
                              bounds=([-5, -20, -30, -30, 0.05, 0.5], [20, 20, 30, 30, 15, 60]))
            if best is None or r.cost < best.cost:
                best = r
    resid = nss(t, best.x) - y
    return {"params": best.x, "rmse_bp": float(np.sqrt(np.mean(resid ** 2)) * 100),
            "max_err_bp": float(np.abs(resid).max() * 100)}


def rolldown_bp(params, tenor: float, horizon_years: float) -> float:
    """Yield fall from sliding down the curve: y(T) - y(T - h), in bp. Positive helps a long position."""
    return float((nss([tenor], params)[0] - nss([tenor - horizon_years], params)[0]) * 100)
