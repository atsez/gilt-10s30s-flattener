"""Reproduce every number: python3 run.py  ->  results/results.md (+ charts when history is present)."""
from __future__ import annotations

import glob
import os

import numpy as np

from gilt import history as H
from gilt import trade as T
from gilt import mark as M
from gilt.curve import fit_nss, rolldown_bp

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, "data", "snapshot_20260814.json")
BBG = os.path.join(HERE, "data", "gilt_history.csv")
BOE = sorted(glob.glob(os.path.join(HERE, "data", "boe", "*.xls*")))
OUT = os.path.join(HERE, "results")


def table(head, rows):
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(r) + " |" for r in rows]


def snapshot_section(snap):
    L = [f"# Results", "", f"Levels as of {snap['trade_date']}, settlement {snap['settle']}. "
         "Quoted yields from Bloomberg; everything else computed here.", "",
         "## 1. Pricer against Bloomberg YAS", ""]
    L += table(["bond", "field", "Bloomberg", "this code", "difference"],
               [[r["bond"], r["field"], f"{r['bloomberg']:.6f}", f"{r['python']:.6f}", f"{r['diff']:+.1e}"]
                for r in T.reconcile(snap)])
    st = T.structure(snap)
    L += ["", "## 2. Structure", ""]
    L += table(["measure", "value"], [
        ["10s30s spread", f"{st['spread_bp']:.2f}bp"],
        ["hedge ratio (10y nominal per 1 of 30y)", f"{st['hedge_ratio']:.4f}"],
        ["convexity, long 30y", f"{st['risk_long']['convexity']:.3f}"],
        ["convexity, DV01-weighted short 10y", f"{st['short_convexity_weighted']:.3f}"],
        ["net convexity", f"{st['net_convexity']:+.3f}"],
        ["convexity ratio", f"{st['convexity_ratio']:.2f}x"]])

    simple, exact = T.carry_simple(snap, st), T.carry_exact(snap, st)
    L += ["", f"## 3. Carry and roll-down, {snap['horizon_days']} days, repo {snap['repo']:.4%}", "",
          "Per 100 nominal:", ""]
    sl, ll, el, eL = simple["legs"]["short_leg"], simple["legs"]["long_leg"], exact["legs"]["short_leg"], exact["legs"]["long_leg"]
    L += table(["component", "10y simple", "30y simple", "10y exact", "30y exact"], [
        ["coupon accrual", f"{sl['coupon']:.4f}", f"{ll['coupon']:.4f}", f"{el['accrual']:.4f}", f"{eL['accrual']:.4f}"],
        ["pull to par", "-", "-", f"{el['pull_to_par']:.4f}", f"{eL['pull_to_par']:.4f}"],
        ["repo on dirty price", f"({sl['repo']:.4f})", f"({ll['repo']:.4f})", f"({el['repo']:.4f})", f"({eL['repo']:.4f})"],
        ["repo saved after coupon", "-", "-", f"{el['coupon_interest']:.4f}", f"{eL['coupon_interest']:.4f}"],
        ["roll-down", f"{sl['roll']:.4f}", f"{ll['roll']:.4f}", f"{el['roll']:.4f}", f"{eL['roll']:.4f}"],
        ["total", f"**{sl['total']:.4f}**", f"**{ll['total']:.4f}**", f"**{el['total']:.4f}**", f"**{eL['total']:.4f}**"]])
    L += ["", "Position, long GBP1m of the 30y against the DV01-matched 10y:", ""]
    L += table(["method", "GBP per quarter", "bp of spread per quarter", "bp per year"], [
        ["simple (spreadsheet)", f"{simple['gbp_per_quarter']:,.0f}", f"{simple['bp_per_quarter']:.2f}", f"{simple['bp_per_quarter'] * 4:.1f}"],
        ["exact (cash flows)", f"{exact['gbp_per_quarter']:,.0f}", f"{exact['bp_per_quarter']:.2f}", f"{exact['bp_per_quarter'] * 4:.1f}"]])
    L += ["", "Bridge from the spreadsheet figure to the exact one (GBP per quarter per GBP1m of 30y):", ""]
    L += table(["step", "GBP"], [[k, f"{v:,.0f}"] for k, v in T.carry_bridge(simple, exact, st["hedge_ratio"])])
    fwd_spread = (eL["forward_yield"] - el["forward_yield"]) * 100
    L += ["", f"Repo-forward yields over the quarter: 10y {el['forward_yield']:.4f}% ({el['carry_bp_yield']:+.2f}bp), "
              f"30y {eL['forward_yield']:.4f}% ({eL['carry_bp_yield']:+.2f}bp). The repo-forward 10s30s is "
              f"{fwd_spread:.2f}bp against {st['spread_bp']:.2f}bp spot, so before roll-down the spread has to fall "
              f"{st['spread_bp'] - fwd_spread:.2f}bp in the quarter just for the flattener to break even."]

    for name, c in (("simple carry", simple), ("exact carry", exact)):
        r = T.risk_and_sizing(snap, st, c)
        if name == "simple carry":
            L += ["", "## 4. Stop, scenarios and sizing", ""]
            L += table(["scenario", "target", "move", "probability"],
                       [[s["name"], f"{s['target_bp']:.2f}bp", f"{s['move_bp']:+.2f}bp", f"{s['prob']:.0%}"] for s in r["scenarios"]])
            L += [""] + table(["measure", "value"], [
                ["stop", f"{snap['stop_bp']:.0f}bp of widening, spread at {r['stop_level_bp']:.2f}bp, "
                         f"{r['above_ten_year_max_bp']:.1f}bp above the ten-year high"],
                ["stop in sd of a 3-month move", f"{r['stop_in_3m_sd']:.2f}"],
                ["reward to risk, to forward / to ten-year mean", f"{r['reward_risk_fwd']:.2f} / {r['reward_risk_mean']:.2f}"],
                ["breakeven probability, to forward / to mean", f"{r['breakeven_p_fwd']:.1%} / {r['breakeven_p_mean']:.1%}"],
                ["expected value before carry", f"{r['ev_before_carry']:+.2f}bp"],
                ["loss at stop", f"GBP{r['loss_at_stop']:,.0f} ({snap['risk_budget']:.1%} of GBP{snap['nav_gbp_m']:.0f}m)"],
                ["position DV01", f"GBP{r['position_dv01']:,.0f} per bp"],
                ["long UKT 5 3/8 2056", f"GBP{r['long_m']:.2f}m"],
                ["short UKT 4 3/4 2035", f"GBP{r['short_m']:.2f}m"],
                ["gross notional", f"GBP{r['gross_m']:.2f}m"]])
            L += ["", "| carry method | EV after one quarter | carry per quarter |", "|---|---|---|"]
        L.append(f"| {name} | {r['ev_after_carry']:+.2f}bp | -GBP{-r['carry_gbp_per_quarter']:,.0f} |")

    x = T.cross_checks(snap)
    L += ["", "## 5. Where the steepness comes from", ""]
    L += table(["measure", "bp"], [
        ["gilt 10s30s", f"{x['gilt_10s30s']:.1f}"], ["SONIA swap 10s30s", f"{x['swap_10s30s']:.1f}"],
        ["gilt-specific (gilt curve less swap curve)", f"{x['gilt_specific']:.1f}"],
        ["gilt less swap yield, 10y / 30y", f"{x['gilt_minus_swap_10y']:.1f} / {x['gilt_minus_swap_30y']:.1f}"],
        ["breakeven inflation 10s30s", f"{x['inflation_part']:.1f}"], ["real yield 10s30s", f"{x['real_part']:.1f}"]])
    return L, st, exact


HISTORY_START = "2016-08-15"   # the ten-year window the trade was judged on


def history_section(full, src, snap, exact):
    full = full.loc[HISTORY_START:]
    curve = full.loc[:snap["trade_date"]]                       # everything up to the entry, nothing after
    s = H.spread_bp(curve)
    L = ["", f"## 6. Spread history ({src}, {s.index[0]:%d %b %Y} to {s.index[-1]:%d %b %Y}, {len(s):,} days)", ""]
    L += table(["window", "obs", "min", "max", "mean", "current percentile"],
               [[r.window, f"{r.obs:,}", f"{r['min']:.1f}", f"{r['max']:.1f}", f"{r['mean']:.1f}", f"{r.percentile:.1%}"]
                for _, r in H.percentile_table(s).iterrows()])
    L += [""] + table(["lookback", "spread then", "change"],
                      [[r.lookback, f"{r.then:.1f}", f"{r.change:+.1f}"] for _, r in H.momentum(s).iterrows()])
    v = H.volatility(s)
    L += ["", f"Daily sd {v['daily_sd']:.2f}bp ({v['annual_sd']:.1f}bp annualised), sd of a 3-month change "
              f"{v['sd_3m_change']:.1f}bp.", "", "### Next-quarter base rates by starting level", ""]
    L += table(["start", "obs", "P(widen > 20bp)", "worst widening", "mean change", "P(narrow)", "P(narrow > 12.5bp)"],
               [[r.start, f"{r.obs:,}", f"{r.p_widen_gt_stop:.1%}", f"{r.worst_widening:+.1f}", f"{r.mean_change:+.1f}",
                 f"{r.p_narrow:.1%}", f"{r.p_narrow_gt_target:.1%}"] for _, r in H.base_rates(s).iterrows()])
    L += ["", "### Is the spread mean-reverting?", ""]
    rows = []
    for name, x in (("full sample", s), ("last 2 years", s.loc[s.index[-1] - np.timedelta64(730, "D"):])):
        r = H.stationarity(x)
        rows.append([name, f"{r['obs']:,}", f"{r['adf_stat']:.2f}", f"{r['adf_p']:.3f}", f"{r['half_life_days']:.0f}"])
    L += table(["sample", "obs", "ADF statistic", "p-value", "AR(1) half-life, days"], rows)

    p = H.pca(curve)
    if p:
        L += ["", f"### PCA of daily curve changes ({p['obs']:,} days, tenors {', '.join(f'{t:g}y' for t in p['tenors'])})", ""]
        L += table(["", "level", "slope", "curvature"],
                   [["variance explained"] + [f"{e:.1%}" for e in p["explained"]],
                    ["10s30s variance explained, cumulative"] + [f"{e:.1%}" for e in p["spread_r2_cumulative"]]] +
                   [[f"loading {t:g}y"] + [f"{p['loadings'][i, k]:+.2f}" for k in range(3)] for i, t in enumerate(p["tenors"])])

    carry_q = exact["bp_per_quarter"]
    bt = H.rule_backtest(s, carry_bp_per_quarter=carry_q)
    L += ["", "### The entry rule, tested on history", "",
          f"Flattener when the spread is in the top decile of its trailing three years; next-day entry; "
          f"exit at a 20bp stop or after one quarter; carry charged at {carry_q:.2f}bp a quarter. "
          "Parameters fixed in advance, not optimised."]
    if len(bt):
        L += [""] + table(["trades", "hit rate", "mean before carry", "mean after carry", "worst", "stopped out",
                           "total after carry"],
                          [[f"{len(bt)}", f"{(bt.pnl_bp > 0).mean():.0%}", f"{bt.gross_bp.mean():+.1f}bp",
                            f"{bt.pnl_bp.mean():+.1f}bp", f"{bt.pnl_bp.min():+.1f}bp", f"{(bt.exit_on == 'stop').sum()}",
                            f"{bt.pnl_bp.sum():+.1f}bp"]])
        bt.to_csv(os.path.join(OUT, "rule_trades.csv"), index=False)
    else:
        L += ["", "No signals in the sample."]

    if src.startswith("Bank of England"):
        day = curve.loc[:snap["trade_date"]].iloc[-1].dropna()
        fit = fit_nss(day.index.to_numpy(float), day.to_numpy(float))
        q = snap["horizon_days"] / 365
        L += ["", f"### Roll-down from a Nelson-Siegel-Svensson fit to the BoE spot curve, {day.name:%d %b %Y}", "",
              f"Fit RMSE {fit['rmse_bp']:.2f}bp, max error {fit['max_err_bp']:.2f}bp.", ""]
        L += table(["leg", "NSS roll-down", "Bloomberg I22 (used above)"],
                   [["10y", f"{rolldown_bp(fit['params'], 10, q):.2f}bp", f"{snap['rolldown_bp']['short_leg']:.2f}bp"],
                    ["30y", f"{rolldown_bp(fit['params'], 30, q):.2f}bp", f"{snap['rolldown_bp']['long_leg']:.2f}bp"]])
    L += since_entry(H.spread_bp(full), s, snap, exact)
    L += bond_mark(full, snap)
    _charts(H.spread_bp(full), s.index[-1], bt, p)
    return L


def since_entry(sf, s, snap, exact):
    """What the spread has done since the trade was put on, on the same data series."""
    post = sf.loc[s.index[-1]:]
    if len(post) < 2:
        return []
    entry, last = post.iloc[0], post.iloc[-1]
    days = (post.index[-1] - post.index[0]).days
    worst = (post - entry).max()
    carry = exact["bp_per_quarter"] * days / 91
    dv01 = snap["nav_gbp_m"] * 1e6 * snap["risk_budget"] / snap["stop_bp"]
    pnl = entry - last + carry
    stop_hit = post[post - entry >= snap["stop_bp"]]
    L = ["", f"## 7. Since entry ({post.index[0]:%d %b %Y} to {post.index[-1]:%d %b %Y}, {days} days, same series)", ""]
    L += table(["measure", "value"], [
        ["spread at entry", f"{entry:.1f}bp"], ["spread now", f"{last:.1f}bp"],
        ["change", f"{last - entry:+.1f}bp ({'flatter, in favour' if last < entry else 'steeper, against'})"],
        ["range since entry", f"{post.min():.1f}bp to {post.max():.1f}bp"],
        ["worst widening against the position", f"{worst:+.1f}bp (stop at +{snap['stop_bp']:.0f}bp)"],
        ["stop touched", f"yes, {stop_hit.index[0]:%d %b %Y}" if len(stop_hit) else "no"],
        ["carry to date (exact)", f"{carry:+.2f}bp"],
        ["P&L to date", f"{pnl:+.1f}bp, about GBP{pnl * dv01:+,.0f} at GBP{dv01:,.0f} DV01"]])
    L += ["", "P&L is approximated from the fitted-curve spread, not the two bonds' own prices."]
    return L


def bond_mark(full, snap):
    """Reprice the two actual bonds off the Bank's curve each day since entry, on the August sizing."""
    st = T.structure(snap)
    r = T.risk_and_sizing(snap, st, T.carry_simple(snap, st))
    m = M.mark(snap, full, r["long_m"], r["short_m"])
    path = m["path"]
    if not len(path):
        return []
    last = path.iloc[-1]
    path.to_csv(os.path.join(OUT, "mark_since_entry.csv"))
    y10 = (last.y_short_leg - snap["short_leg"]["yield"]) * 100
    y30 = (last.y_long_leg - snap["long_leg"]["yield"]) * 100
    nav = snap["nav_gbp_m"] * 1e6
    L = ["", f"### The two bonds, repriced off the Bank's curve (to {path.index[-1]:%d %b %Y})", "",
         f"Each bond keeps its August spread to the curve ({m['basis_bp']['short_leg']:+.1f}bp for the 2035, "
         f"{m['basis_bp']['long_leg']:+.1f}bp for the 2056). Position as sized in section 4, financed at repo, coupons credited.", ""]
    L += table(["measure", "value"], [
        ["10s30s on the two bonds", f"{m['entry_spread']:.1f}bp to {last.spread_bp:.1f}bp ({last.spread_bp - m['entry_spread']:+.1f}bp)"],
        ["UKT 4 3/4 2035 (short)", f"{y10:+.1f}bp, P&L GBP{last.pnl_short_leg:+,.0f}"],
        ["UKT 5 3/8 2056 (long)", f"{y30:+.1f}bp, P&L GBP{last.pnl_long_leg:+,.0f}"],
        ["total P&L", f"GBP{last.pnl_gbp:+,.0f}, {last.pnl_gbp / nav:+.2%} of NAV, "
                      f"{last.pnl_gbp / (nav * snap['risk_budget']):.2f}x the risk budget"],
        ["share from the short 2035", f"{last.pnl_short_leg / last.pnl_gbp:.0%}"],
        ["worst move against", f"{m['worst_against_bp']:+.2f}bp, worst P&L GBP{m['worst_pnl_gbp']:+,.0f}"],
        ["best point", f"GBP{path.pnl_gbp.max():+,.0f} on {path.pnl_gbp.idxmax():%d %b %Y}, spread {path.spread_bp.min():.1f}bp at its low"]])
    return L


def _charts(s, entry_date, bt, p):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(s.index, s.values, lw=0.8, color="#1f4e79", label="10s30s")
    ax.plot(s.index, s.rolling(756).quantile(0.9), lw=0.8, ls="--", color="#c55a11", label="trailing 3y 90th percentile")
    if len(bt):
        ax.scatter(bt.entry_date, bt.entry, s=14, color="#c00000", zorder=3, label="rule entries")
    ax.axvline(entry_date, color="black", lw=0.8, ls=":", label=f"trade entry {entry_date:%d %b %Y}")
    ax.axhline(0, color="grey", lw=0.5)
    ax.set_ylabel("bp"), ax.set_title("UK gilt 10s30s spread"), ax.legend(frameon=False, fontsize=8)
    fig.tight_layout(), fig.savefig(os.path.join(OUT, "spread.png"), dpi=150), plt.close(fig)
    if p:
        fig, ax = plt.subplots(figsize=(6, 3.5))
        for k, name in enumerate(("level", "slope", "curvature")):
            ax.plot(p["tenors"], p["loadings"][:, k], marker="o", label=f"{name} ({p['explained'][k]:.0%})")
        ax.axhline(0, color="grey", lw=0.5), ax.set_xlabel("tenor (years)"), ax.legend(frameon=False, fontsize=8)
        ax.set_title("PCA loadings, daily curve changes")
        fig.tight_layout(), fig.savefig(os.path.join(OUT, "pca.png"), dpi=150), plt.close(fig)


def main():
    os.makedirs(OUT, exist_ok=True)
    snap = T.load_snapshot(SNAP)
    L, st, exact = snapshot_section(snap)
    if os.path.exists(BBG):
        L += history_section(H.load_bloomberg_csv(BBG), "Bloomberg generic yields", snap, exact)
    elif BOE:
        L += history_section(H.load_boe(BOE), "Bank of England fitted spot curve", snap, exact)
    else:
        L += ["", "## 6. Spread history", "", "Not run: no history file in data/. See data/README.md."]
    text = "\n".join(L) + "\n"
    open(os.path.join(OUT, "results.md"), "w").write(text)
    print(text)


if __name__ == "__main__":
    main()
