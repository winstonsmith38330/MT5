# Market-data and chart semantics

`MetaTrader5` is a Windows-only optional package. The exporter uses its documented `initialize`, `account_info`, `terminal_info`, `symbol_info`, `symbols_get`, `symbol_select`, `copy_ticks_range`, `copy_rates_range` and `shutdown` operations, never `order_send`. The Python API has no compiler or Strategy Tester method; those are native MCP or CLI operations.

## Tick export

Exports cover an explicit timezone-aware interval, converted to UTC, with an exclusive end. They are bounded to 32 days / two million ticks and request disjoint one-hour millisecond intervals. Each row has a persistent `sequence`, original `time_msc`, UTC presentation, `bid`, `ask`, `last`, `volume`, `flags`, `volume_real`. Equal-time ticks are not deduplicated or reordered. A backwards timestamp fails export. Both quote sides and the original flags remain available; OHLC comparisons must specify bid/ask/last and broker rules.

The API materializes one chunk at a time; the exporter streams these chunks to CSV. Dense chunks can still use significant memory. An exceeded tick limit stops before the next whole chunk, preserving equal-time records in completed chunks and marking TRUNCATED/incomplete coverage; reference bars still export. A broker API failure fails honestly and leaves partial local evidence. Request smaller intervals to obtain complete ticks. Empty results produce DATA_MISSING. API retrieval and exported row counts do not prove continuous history or absence of broker gaps. Cross-check journals, real-tick coverage, missing sessions and source constraints before drawing conclusions. No `.tkc` decoder is supplied: actual `.tkc` caches are proprietary binary, not CSV.

M15, H4 and D1 bars come directly from the broker, with 120 days of requested warmup. Broker availability and terminal bar limits can truncate that request. Set the dedicated terminal's history limits appropriately and inspect first/last timestamps and SMA55 warmup. Symbol specification and requested range/quality metadata are exported alongside the data.

## Time and reference math

MT5 Python history timestamps are handled as UTC instants. The broker's session/day boundaries, DST, rollover and H4 anchoring must be identified from actual broker data and native `get_time_information` where installed. OS timezone does not establish broker chart time. The export manifest leaves the broker chart timezone UNKNOWN rather than inventing it.

Offline charts use completed **broker H4 bars**, SMA5 and SMA55 of closing prices, and classical previous-broker-D1 pivots: P=(high+low+close)/3, R1=2P-low, S1=2P-high. D1 values are shifted one broker daily bar, then joined as-of to H4 opens. No UTC midnight resampling is used. An indicator label is reference mathematics, not a claim that Johnavan/Kyrie uses that formula, applied price, period, shift or session. Match actual EA/broker definitions before any independent reconstruction claim.

Final OHLC cannot reconstruct every intrabar SMA crossing/event. The current bar changes as ticks arrive; actual tester tick sequence and EA indicator snapshots/audit events may be needed. An offline reference chart does not validate exact signal timing or execution.

## Audit adapters and charts

Default markers CSV columns: `time` (UTC ISO8601 or epoch seconds), `price`, `label`. For another format, pass a JSON mapping from those canonical names to actual CSV column names, such as `examples/marker-schema.json`. Convert naive broker wall-clock times explicitly using confirmed broker rules before charting; numeric markers use epoch seconds, not milliseconds. No strategy-specific fields or values are invented. Missing D1/audit files or insufficient warmup are reported as DATA_MISSING; an explicitly requested nonexistent file fails the job.

```powershell
./.venv/Scripts/mt5-research.exe --workspace local chart --h4 outputs/RUN/EURUSD/market-data/H4.csv --d1 outputs/RUN/EURUSD/market-data/D1.csv --markers audits/actual-markers.csv --schema marker-schema.json --output outputs/RUN/EURUSD/audited-charts
```

Paths are relative to `local`. The CLI command writes self-contained HTML (no chart CDN) and a PNG using a headless plotting backend, enriched reference CSV and chart manifest. Inputs are limited to 32 MiB and 100,000 rows; PNG displays the last 3,000 candles. HTML and CSV retain the full accepted input. Unknown EA audit schemas require a supplied mapping or explicit local conversion, not made-up Johnavan data. Synthetic test markers are labelled SYNTHETIC_TEST and are not broker records.
