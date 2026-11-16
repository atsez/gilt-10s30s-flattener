"""Spread history: loaders, entry context, conditional base rates, stationarity, PCA and a rule test.

Two data sources are supported (see data/README.md):
- a Bloomberg export: a CSV with a date column and generic yields such as GUKG10 and GUKG30
- the Bank of England nominal yield curve files (glcnominalddata), sheet "4. spot curve"
Yields are in percent. Spreads are in basis points.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd


# ------------------------------------------------------------------ loaders
def load_bloomberg_csv(path: str) -> pd.DataFrame:
    """CSV with a date column and yield columns named like GUKG10 / GUKG30 (any name with the tenor)."""
    raw = pd.read_csv(path)
    first = str(raw.iloc[0, 0])
    iso = len(first) >= 10 and first[4] == "-"                     # 2026-08-14 vs 14/08/2026
    raw = raw.set_index(pd.to_datetime(raw.iloc[:, 0], dayfirst=not iso)).iloc[:, 1:]
    cols = {}
    for c in raw.columns:
        m = re.search(r"(\d+(?:\.\d+)?)", str(c))
        if m:
            cols[c] = float(m.group(1))
    out = raw[list(cols)].rename(columns=cols).apply(pd.to_numeric, errors="coerce")
    return out.sort_index().dropna(how="all")


def load_boe(paths: list[str], sheet_hint: str = "spot curve") -> pd.DataFrame:
    """Bank of England glcnominalddata workbooks. Finds the 'years:' header row rather than assuming a layout."""
    frames = []
    for p in paths:
        xl = pd.ExcelFile(p)
        sheet = next(s for s in xl.sheet_names if sheet_hint in s.lower() and "short" not in s.lower())
        df = xl.parse(sheet, header=None)
        hdr = next(i for i, v in df.iloc[:, 0].items() if isinstance(v, str) and v.strip().lower().startswith("years"))
        tenors = pd.to_numeric(df.iloc[hdr, 1:], errors="coerce")
        body = df.iloc[hdr + 1:]
        first = body.iloc[:, 0]
        dates = pd.to_datetime(first.where(first.map(lambda v: hasattr(v, "year"))), errors="coerce")
        body = body[dates.notna()]
        block = body.iloc[:, 1:].apply(pd.to_numeric, errors="coerce")
        block.columns = tenors.values
        block.index = pd.to_datetime(body.iloc[:, 0].tolist())
        frames.append(block.loc[:, block.columns.notna()])
    out = pd.concat(frames).sort_index()
    return out[~out.index.duplicated(keep="last")].dropna(how="all")


def spread_bp(curve: pd.DataFrame, short: float = 10, long: float = 30) -> pd.Series:
    return ((curve[long] - curve[short]) * 100).dropna().rename(f"{short:g}s{long:g}s")


# ------------------------------------------------------------------ entry context
def percentile_table(s: pd.Series, windows=(10, 5, 2, 1)) -> pd.DataFrame:
    end, rows = s.index[-1], []
    for w in windows:
        x = s.loc[end - pd.DateOffset(years=w):]
        rows.append({"window": f"{w} year{'s' if w > 1 else ''}", "obs": len(x), "min": x.min(), "max": x.max(), "mean": x.mean(),
                     "percentile": (x <= x.iloc[-1]).mean()})
    return pd.DataFrame(rows)


def momentum(s: pd.Series, months=(1, 3, 6, 12, 24)) -> pd.DataFrame:
    end, rows = s.index[-1], []
    for m in months:
        then = s.loc[:end - pd.DateOffset(months=m)]
        if len(then):
            rows.append({"lookback": f"{m} months", "then": then.iloc[-1], "change": s.iloc[-1] - then.iloc[-1]})
    return pd.DataFrame(rows)


def forward_change(s: pd.Series, days: int = 91) -> pd.Series:
    """Change from each date to the first observation at least `days` calendar days later."""
    idx = s.index.searchsorted(s.index + pd.Timedelta(days=days))
    ok = idx < len(s)
    return pd.Series(s.to_numpy()[idx[ok]] - s.to_numpy()[ok], index=s.index[ok])


def volatility(s: pd.Series, days: int = 91) -> dict:
    d = s.diff().dropna()
    return {"daily_sd": d.std(), "annual_sd": d.std() * np.sqrt(252), "sd_3m_change": forward_change(s, days).std()}


def base_rates(s: pd.Series, levels=(None, 60, 65, 70, 72), stop: float = 20, target: float = 12.5,
               days: int = 91) -> pd.DataFrame:
    """What the spread did over the next quarter, conditional on where it started."""
    fc, rows = forward_change(s, days), []
    for lv in levels:
        x = fc if lv is None else fc[s.loc[fc.index] > lv]
        if not len(x):
            continue
        rows.append({"start": "any level" if lv is None else f"above {lv}bp", "obs": len(x),
                     "p_widen_gt_stop": (x > stop).mean(), "worst_widening": x.max(), "mean_change": x.mean(),
                     "p_narrow": (x < 0).mean(), "median_change": x.median(),
                     "p_narrow_gt_target": (x < -target).mean()})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ is it mean-reverting at all?
def stationarity(s: pd.Series) -> dict:
    """ADF test and AR(1) half-life. A rich spread is only a trade if it tends to come back."""
    import warnings
    from statsmodels.tsa.stattools import adfuller
    if np.ptp(s.dropna().to_numpy()) < 1e-9:
        return {"adf_stat": np.nan, "adf_p": np.nan, "ar1_coef": np.nan, "half_life_days": np.nan, "obs": len(s)}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        stat, p, *_ = adfuller(s.dropna(), autolag="AIC")
    ds, lag = s.diff().dropna(), s.shift(1).dropna()
    lag = lag.loc[ds.index]
    b = np.polyfit(lag.to_numpy(), ds.to_numpy(), 1)[0]
    half_life = -np.log(2) / np.log(1 + b) if -1 < b < 0 else np.inf
    return {"adf_stat": stat, "adf_p": p, "ar1_coef": 1 + b, "half_life_days": half_life, "obs": len(s)}


# ------------------------------------------------------------------ PCA: is 10s30s a slope trade?
def pca(curve: pd.DataFrame, tenors=(2, 5, 10, 20, 30), spread=(10, 30)) -> dict | None:
    have = [t for t in tenors if t in curve.columns]
    if len(have) < 4:
        return None
    dy = (curve[have].dropna().diff().dropna()) * 100                 # bp changes
    dy = dy - dy.mean()
    vals, vecs = np.linalg.eigh(np.cov(dy.T))
    order = np.argsort(vals)[::-1]
    vals, vecs = vals[order], vecs[:, order]
    for k in range(vecs.shape[1]):                                   # sign convention: level up, slope steepens
        ref = vecs[:, k].sum() if k == 0 else vecs[-1, k] - vecs[0, k]
        if ref < 0:
            vecs[:, k] *= -1
    scores = dy.to_numpy() @ vecs
    ds = (dy[spread[1]] - dy[spread[0]]).to_numpy()
    r2 = []
    for k in range(3):
        beta = np.linalg.lstsq(scores[:, :k + 1], ds, rcond=None)[0]
        r2.append(1 - np.var(ds - scores[:, :k + 1] @ beta) / np.var(ds))
    return {"tenors": have, "explained": vals[:3] / vals.sum(), "loadings": vecs[:, :3],
            "spread_r2_cumulative": r2, "obs": len(dy)}


# ------------------------------------------------------------------ the entry rule, tested out of sample
def rule_backtest(s: pd.Series, lookback: int = 756, pct: float = 0.90, hold_days: int = 91,
                  stop: float = 20, carry_bp_per_quarter: float = 0.0) -> pd.DataFrame:
    """Flattener when the spread is in the top decile of its trailing three years.

    The signal on day t uses only data up to t; the trade is put on at the next day's close.
    Trades do not overlap. Exit at the stop or after `hold_days`. P&L is in bp of spread,
    with carry charged pro rata (pass the negative carry as a negative number).
    """
    v, idx, trades, i = s.to_numpy(), s.index, [], lookback
    while i < len(s) - 1:
        window = v[i - lookback + 1:i + 1]
        if (window <= v[i]).mean() >= pct:
            e = i + 1
            j, reason = e, "time"
            while j + 1 < len(s) and (idx[j + 1] - idx[e]).days <= hold_days:
                j += 1
                if v[j] - v[e] >= stop:
                    reason = "stop"
                    break
            days = (idx[j] - idx[e]).days
            trades.append({"entry_date": idx[e], "exit_date": idx[j], "entry": v[e], "exit": v[j], "exit_on": reason,
                           "gross_bp": v[e] - v[j], "pnl_bp": v[e] - v[j] + carry_bp_per_quarter * days / 91})
            i = j + 1
        else:
            i += 1
    return pd.DataFrame(trades)
