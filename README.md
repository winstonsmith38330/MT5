# MT5 research infrastructure

Research tools for Nicolas: local MQL5 compilation, sequential historical Strategy Tester runs, broker-data exports and offline HTML/PNG charts. This repository contains no strategy, broker password, terminal binary, MT5 licence or historical tick cache. No account-order tool is exposed.

**A cloud checkout/GitHub connection does not connect to Nicolas's Windows terminal, demo account, filesystem or localhost MCP server.** Cloud verification uses synthetic data and explicitly labelled MOCK mode. Windows compilation, broker history, native capability discovery and tester execution require local activation.

## Quick start

Cloud / Linux (verified with Python **3.12.14**):

```bash
bash scripts/install-cloud.sh
/workspace/mt5-venv/bin/mt5-research --workspace /workspace/MT5/local health
/workspace/mt5-venv/bin/mt5-research --workspace /workspace/MT5/local gateway --mock
```

The last command stays in the foreground at loopback port 8765. It does not connect to MT5. Installation does not install the Windows-only MetaTrader5 wheel. `requirements-cloud.lock` pins the tested portable dependency versions; `.[windows]` is a separate optional dependency group. Python 3.12 is the reference version, not a claim that every permitted newer interpreter has been tested.

Windows: follow [WINDOWS_SETUP](docs/WINDOWS_SETUP.md). Local Codex can connect directly to the native MCP servers if installed capabilities suffice; a gateway is only necessary for hosted access, bounded fallback jobs or offline charts. Hosted ChatGPT Work: follow [CHATGPT_WORK_CONNECTION](docs/CHATGPT_WORK_CONNECTION.md).

## Layout

- `src/mt5_research`: gateway, allowlist, jobs, Windows worker, exporter and charts.
- `examples`: templates only; real values go under ignored `local/` or into the Windows secret store/process environment.
- `scripts/windows`: installation, gateway startup and path discovery.
- `tests`: offline security, parsing, jobs, OAuth and actual MCP transport tests; no orders.
- `docs`: activation, protocol boundaries, reference mathematics, limitations and completion evidence.

## Workflow

1. Discover actual Windows terminal/editor schemas and broker symbol aliases.
2. Supply the actual EA source/includes and its preset; **DATA_MISSING** is correct until supplied.
3. Compile into a new output directory and verify diagnostics plus a fresh nonempty EX5.
4. Run EURUSD then NAS100 on H4, 2025-01-01 to 2025-02-01 if history exists: USD 3000, requested tester leverage 1:100, real ticks, no optimization, no visual mode. Set 0.50 percent risk only with the EA's confirmed percent-input mapping.
5. Collect reports, fresh relevant logs/audits, symbol specs, bounded ticks, M15/H4/D1 bars, quality warnings and charts under `local/outputs/<run-id>/`.
6. Review mechanical evidence before researching performance. Missing audits, zero trades, absent reports/settings/history or unknown indicator math are **INCONCLUSIVE** or an explicit mechanical failure; never strategy validation.

The worker uses a dedicated portable terminal beneath the research workspace and refuses to terminate any pre-existing session. Jobs are sequential and their IDs are local to a gateway process. Long jobs require polling; restart loses in-memory job status but keeps filesystem outputs. Cancelling/timeout kills only the process the worker started. See [ARCHITECTURE](docs/ARCHITECTURE.md) for native adapter limits and [DATA_AND_CHARTS](docs/DATA_AND_CHARTS.md) for data fidelity.
