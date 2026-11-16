# Data

`snapshot_20260814.json` holds the quoted inputs for the trade: both gilts' terms and yields, plus repo,
roll-down, the forward spread and the swap and breakeven levels, all from the Bloomberg close on
14 August 2026. Bloomberg's own risk figures are stored only so the pricer can be checked against them.

The spread history is not redistributed. The history layer runs on either of two sources. If both are
present, the Bloomberg file is used.

## Option 1: Bloomberg export (matches the levels above)

Export daily `PX_LAST` for `GUKG2 Index`, `GUKG5 Index`, `GUKG10 Index`, `GUKG20 Index` and `GUKG30 Index`
over 15 Aug 2016 to 14 Aug 2026 (Excel add-in, BDH), and save it as `data/gilt_history.csv`:

```
Date,GUKG2,GUKG5,GUKG10,GUKG20,GUKG30
2016-08-15,0.12,0.25,0.55,1.10,1.30
...
```

Only GUKG10 and GUKG30 are required. The other tenors switch on the PCA. Any column name that contains the
tenor works, and dates may be ISO or day-first.

## Option 2: Bank of England fitted curve (free)

From the Bank of England yield curve archive, download the nominal daily data
(`glcnominalddata.zip`), unzip it and put the workbooks in `data/boe/`. The loader reads the
`4. spot curve` sheet.

These are zero-coupon spot yields from the Bank's fitted curve, not the yields of benchmark bonds, so
the spread levels will differ by a few basis points from the Bloomberg generic series. This path also
fits a Nelson-Siegel-Svensson curve on the snapshot date and compares its roll-down with the figures
used in the trade.
