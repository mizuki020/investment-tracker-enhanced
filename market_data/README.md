# Market data foundation v0.1 (offline first)

## Status
This is a **CSV ingestion and indicator calculation module**, NOT an automatic price fetcher.
It does not query live exchanges, scrape websites, or send brokerage orders.
Do not present sample or synthetic prices as actual 9983 market data.

## Input contract
UTF-8 CSV, chronological daily bars with header:
`date,open,high,low,close,volume`

- `date`: ISO `YYYY-MM-DD` trading date in Asia/Tokyo
- prices: positive finite values, with `low <= open,close <= high`
- `volume`: nonnegative integer
- dates: strictly increasing and unique
- prices must use a consistent adjustment basis (adjusted or unadjusted)
- provider identity is required in CLI metadata, but not independently authenticated

## Example (use your own licensed and verified CSV)
```bash
python -m market_data.indicators \
  --csv /path/to/verified_9983_daily.csv \
  --ticker 9983 \
  --as-of 2026-10-30 \
  --source "provider-name-and-dataset" \
  --retrieved-at "2026-11-01T10:30:00+09:00" \
  --price-basis unadjusted
```

Output: JSON containing last verified OHLCV, last bar date, source,
retrieval timestamp, indicator values and warnings.
Indicators return `null` during warmup, not invented numbers.

## Indicator definitions
- SMA: 5, 25, 75 trading days
- RSI: Wilder 14, neutral 50 if both average gains and losses are zero
- MACD: EMA 12 minus EMA 26; signal EMA 9 of MACD; histogram MACD minus signal
- Bollinger Bands: SMA 20 ± 2 × population standard deviation

EMA starts from the initial period SMA. Vendor chart values may differ
because of seed, adjustment basis, rounding and historical depth.

## Point-in-time safeguards and limitations
`--as-of` excludes bars dated after the cutoff, including for indicator warmup.
**This alone does not guarantee no look-ahead bias**: the CSV may contain
revised, adjusted or late-published data that were not available on the
historical decision date. The future provider adapter must store original
publication/availability timestamps, provider retrieval timestamps, adjustment
metadata and immutable snapshots before backtesting.

For daily bars, do not assume a bar was available before the market close.
Data rights, exchange delay, corporate actions, and provider uptime must
be evaluated before enabling automated acquisition.

## Run tests
```bash
python -m unittest discover -s tests -p 'test_market_data_indicators.py' -v
```

## Next steps
1. Choose and validate a licensed Japanese equity OHLCV provider.
2. Implement provider adapter with retry/rate-limit handling and immutable raw snapshots.
3. Compare calculated indicators with independently verified reference values.
4. Connect validated JSON to stock-analysis-triad as evidence, not as an order.
