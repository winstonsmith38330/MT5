# Handover checklist

## CLOUD VERIFIED

- Python 3.12.14 reference interpreter; pinned platform-independent dependencies installed, editable package importable.
- Offline tests cover allowlists, path/symlink/alternate-stream rejection, secret redaction, tester/preset generation, serial jobs/cancellation/errors, compiler freshness using fixtures, tick ordering/duplicates/chunks/bounds, reference math/chart parsing, demo/path guard, process ownership and OAuth signature/scope/audience/expiry.
- Actual loopback MCP HTTP initialization/discovery/calls, MOCK health, compile refusal, async chart job/status and PNG retrieval tested using synthetic CSV input.
- Synthetic two-asset pipeline checks EURUSD-before-NAS100, manifests, fresh-report collection, scoped journals and HTML/PNG outputs. Its MOCK_EX5 and MOCK reports are test fixtures, not usable binaries/results.
- Official MetaTrader MCP/config/capabilities/compiler/startup pages and OpenAI tunnel/custom-MCP connection guide fetched and checked on 2026-10-08.
- No Windows-only wheel installed on Linux. No proprietary binaries, real reports/history, secret values or strategy implemented/committed.

Current test command/result: `python -m pytest -q`: **33 passed** (one MCP SDK deprecation warning); final handover records the latest count. `pip check`: no broken requirements.

## WINDOWS ACTION REQUIRED

- Install official dedicated portable terminal/editor below the research root; confirm actual paths/data directory and demo login locally. Set no automated account trading/DLL access and use an empty profile.
- Install Python 3.12 and `.[windows]`; run the offline suite on Windows.
- Obtain actual native endpoints/API keys in the application UI, bind tokens locally, discover and review actual schemas/capabilities. Review narrowly scoped native policies or direct local Codex allowed tools.
- Supply actual EA/source/includes/preset and broker symbol aliases; confirm the EA's percent risk input if applicable. Availability of real-tick history and account/tester leverage/currency must be checked.
- Activate local gateway/Codex mode; for hosted Work, create/associate the real tunnel and keep the official client running, or provision authenticated HTTPS/OAuth and test the supported connection flow.
- Review/save the cloud environment draft and publish its snapshot in environment settings. Draft saving is not publication or a fresh-task restore test.

## NOT RUN

- Actual installed MT5 schema discovery or native tool invocation; no terminal is exposed to cloud.
- Real MetaEditor compilation/EX5, Windows script execution, tester runs, broker data retrieval and EA audit collection.
- Hosted native tester mutation/export adapters: unavailable until real schemas are supplied; implemented CLI/Python fallback jobs cover the workflow.
- Real tunnel, Work plugin association, IdP OAuth round trip, public reverse proxy or hosted artifact transfer from Nicolas's machine.
- Trading-rule changes, optimization, live/demo-account order placement and claims about Johnavan/Kyrie performance.

Missing audit formats/markers, zero trades or missing mechanical evidence remain DATA_MISSING/INCONCLUSIVE. Native capability omissions do not silently become successful tests.
