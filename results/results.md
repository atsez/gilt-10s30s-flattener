# Results

Levels as of 2026-08-14, settlement 2026-08-17. Quoted yields from Bloomberg; everything else computed here.

## 1. Pricer against Bloomberg YAS

| bond | field | Bloomberg | this code | difference |
|---|---|---|---|---|
| UKT 4 3/4 22-Oct-2035 | clean | 98.027000 | 98.026997 | -3.0e-06 |
| UKT 4 3/4 22-Oct-2035 | dirty | 99.545440 | 99.545440 | -4.1e-07 |
| UKT 4 3/4 22-Oct-2035 | accrued | 1.518440 | 1.518443 | +2.6e-06 |
| UKT 4 3/4 22-Oct-2035 | mod_duration | 7.232015 | 7.232015 | +2.9e-07 |
| UKT 4 3/4 22-Oct-2035 | dv01 | 7.199142 | 7.199141 | -5.9e-07 |
| UKT 4 3/4 22-Oct-2035 | convexity | 0.636083 | 0.636083 | +4.5e-07 |
| UKT 5 3/8 31-Jan-2056 | clean | 94.436000 | 94.436004 | +4.4e-06 |
| UKT 5 3/8 31-Jan-2056 | dirty | 94.684300 | 94.684306 | +6.0e-06 |
| UKT 5 3/8 31-Jan-2056 | accrued | 0.248300 | 0.248302 | +1.6e-06 |
| UKT 5 3/8 31-Jan-2056 | mod_duration | 14.247407 | 14.247407 | +4.9e-07 |
| UKT 5 3/8 31-Jan-2056 | dv01 | 13.490058 | 13.490059 | +9.1e-07 |
| UKT 5 3/8 31-Jan-2056 | convexity | 3.088837 | 3.088837 | -3.2e-07 |

## 2. Structure

| measure | value |
|---|---|
| 10s30s spread | 74.98bp |
| hedge ratio (10y nominal per 1 of 30y) | 1.8738 |
| convexity, long 30y | 3.089 |
| convexity, DV01-weighted short 10y | 1.192 |
| net convexity | +1.897 |
| convexity ratio | 2.59x |

## 3. Carry and roll-down, 91 days, repo 3.7308%

Per 100 nominal:

| component | 10y simple | 30y simple | 10y exact | 30y exact |
|---|---|---|---|---|
| coupon accrual | 1.1842 | 1.3401 | 1.1828 | 1.3291 |
| pull to par | - | - | 0.0457 | 0.0121 |
| repo on dirty price | (0.9259) | (0.8807) | (0.9259) | (0.8807) |
| repo saved after coupon | - | - | 0.0061 | 0.0000 |
| roll-down | 0.1152 | 0.0054 | 0.1128 | 0.0054 |
| total | **0.3735** | **0.4648** | **0.4214** | **0.4659** |

Position, long GBP1m of the 30y against the DV01-matched 10y:

| method | GBP per quarter | bp of spread per quarter | bp per year |
|---|---|---|---|
| simple (spreadsheet) | -2,351 | -1.74 | -7.0 |
| exact (cash flows) | -3,238 | -2.40 | -9.6 |

Bridge from the spreadsheet figure to the exact one (GBP per quarter per GBP1m of 30y):

| step | GBP |
|---|---|
| Spreadsheet carry and roll | -2,351 |
| Coupon accrual on actual/actual, not /365 | -82 |
| Pull to par on discount bonds | -736 |
| Repo saved after the 2035 coupon is paid | -114 |
| Roll-down repriced exactly, not yield x DV01 | 44 |
| Exact carry and roll | -3,238 |
| Unexplained | -0 |

Repo-forward yields over the quarter: 10y 5.0638% (+4.39bp), 30y 5.8041% (+3.44bp). The repo-forward 10s30s is 74.03bp against 74.98bp spot, so before roll-down the spread has to fall 0.95bp in the quarter just for the flattener to break even.

## 4. Stop, scenarios and sizing

| scenario | target | move | probability |
|---|---|---|---|
| Bull - partial reversion | 60.00bp | +14.98bp | 30% |
| Base - forward realised | 62.45bp | +12.53bp | 35% |
| Bear - stop | 94.98bp | -20.00bp | 35% |

| measure | value |
|---|---|
| stop | 20bp of widening, spread at 94.98bp, 5.7bp above the ten-year high |
| stop in sd of a 3-month move | 1.50 |
| reward to risk, to forward / to ten-year mean | 0.63 / 1.24 |
| breakeven probability, to forward / to mean | 61.5% / 44.7% |
| expected value before carry | +1.88bp |
| loss at stop | GBP500,000 (0.5% of GBP100m) |
| position DV01 | GBP25,000 per bp |
| long UKT 5 3/8 2056 | GBP18.53m |
| short UKT 4 3/4 2035 | GBP34.73m |
| gross notional | GBP53.26m |

| carry method | EV after one quarter | carry per quarter |
|---|---|---|
| simple carry | +0.14bp | -GBP43,578 |
| exact carry | -0.52bp | -GBP60,011 |

## 5. Where the steepness comes from

| measure | bp |
|---|---|
| gilt 10s30s | 75.0 |
| SONIA swap 10s30s | 43.5 |
| gilt-specific (gilt curve less swap curve) | 31.5 |
| gilt less swap yield, 10y / 30y | 41.1 / 72.6 |
| breakeven inflation 10s30s | 0.8 |
| real yield 10s30s | 74.2 |

## 6. Spread history (Bank of England fitted spot curve, 15 Aug 2016 to 14 Aug 2026, 2,527 days)

| window | obs | min | max | mean | current percentile |
|---|---|---|---|---|---|
| 10 years | 2,527 | -56.0 | 104.1 | 50.4 | 93.2% |
| 5 years | 1,262 | -56.0 | 104.1 | 47.9 | 86.4% |
| 2 years | 507 | 40.7 | 104.1 | 75.5 | 66.1% |
| 1 year | 254 | 65.3 | 104.1 | 81.4 | 62.6% |

| lookback | spread then | change |
|---|---|---|
| 1 months | 76.1 | +5.4 |
| 3 months | 72.2 | +9.3 |
| 6 months | 82.5 | -1.0 |
| 12 months | 99.7 | -18.2 |
| 24 months | 62.3 | +19.1 |

Daily sd 2.81bp (44.6bp annualised), sd of a 3-month change 15.4bp.

### Next-quarter base rates by starting level

| start | obs | P(widen > 20bp) | worst widening | mean change | P(narrow) | P(narrow > 12.5bp) |
|---|---|---|---|---|---|---|
| any level | 2,463 | 8.7% | +67.9 | +0.2 | 51.5% | 16.0% |
| above 60bp | 703 | 3.6% | +32.3 | -2.9 | 66.7% | 15.5% |
| above 65bp | 518 | 1.2% | +24.2 | -3.6 | 68.1% | 17.2% |
| above 70bp | 332 | 0.6% | +21.8 | -4.1 | 69.9% | 20.8% |
| above 72bp | 302 | 0.7% | +21.8 | -3.7 | 68.2% | 18.9% |

### Is the spread mean-reverting?

| sample | obs | ADF statistic | p-value | AR(1) half-life, days |
|---|---|---|---|---|
| full sample | 2,527 | -2.11 | 0.240 | 86 |
| last 2 years | 507 | -1.70 | 0.429 | 65 |

### PCA of daily curve changes (2,526 days, tenors 2y, 5y, 10y, 20y, 30y)

|  | level | slope | curvature |
|---|---|---|---|
| variance explained | 88.4% | 10.2% | 1.3% |
| 10s30s variance explained, cumulative | 0.5% | 69.9% | 98.7% |
| loading 2y | +0.38 | -0.62 | -0.56 |
| loading 5y | +0.44 | -0.41 | +0.22 |
| loading 10y | +0.46 | -0.05 | +0.69 |
| loading 20y | +0.47 | +0.39 | -0.02 |
| loading 30y | +0.48 | +0.54 | -0.39 |

### The entry rule, tested on history

Flattener when the spread is in the top decile of its trailing three years; next-day entry; exit at a 20bp stop or after one quarter; carry charged at -2.40bp a quarter. Parameters fixed in advance, not optimised.

| trades | hit rate | mean before carry | mean after carry | worst | stopped out | total after carry |
|---|---|---|---|---|---|---|
| 11 | 64% | +0.8bp | -1.6bp | -18.7bp | 0 | -17.7bp |

### Roll-down from a Nelson-Siegel-Svensson fit to the BoE spot curve, 14 Aug 2026

Fit RMSE 1.34bp, max error 7.25bp.

| leg | NSS roll-down | Bloomberg I22 (used above) |
|---|---|---|
| 10y | 2.58bp | 1.60bp |
| 30y | -0.32bp | 0.04bp |

## 7. Since entry (14 Aug 2026 to 12 Nov 2026, 90 days, same series)

| measure | value |
|---|---|
| spread at entry | 81.5bp |
| spread now | 44.2bp |
| change | -37.2bp (flatter, in favour) |
| range since entry | 40.2bp to 82.0bp |
| worst widening against the position | +0.6bp (stop at +20bp) |
| stop touched | no |
| carry to date (exact) | -2.37bp |
| P&L to date | +34.8bp, about GBP+871,233 at GBP25,000 DV01 |

P&L is approximated from the fitted-curve spread, not the two bonds' own prices.

### The two bonds, repriced off the Bank's curve (to 12 Nov 2026)

Each bond keeps its August spread to the curve (+3.1bp for the 2035, +4.9bp for the 2056). Position as sized in section 4, financed at repo, coupons credited.

| measure | value |
|---|---|
| 10s30s on the two bonds | 75.0bp to 47.8bp (-27.2bp) |
| UKT 4 3/4 2035 (short) | +21.8bp, P&L GBP+427,155 |
| UKT 5 3/8 2056 (long) | -5.4bp, P&L GBP+217,700 |
| total P&L | GBP+644,855, +0.64% of NAV, 1.29x the risk budget |
| share from the short 2035 | 66% |
| worst move against | +0.35bp, worst P&L GBP-8,701 |
| best point | GBP+713,230 on 28 Oct 2026, spread 45.0bp at its low |
