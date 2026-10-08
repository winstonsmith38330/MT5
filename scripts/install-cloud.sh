#!/usr/bin/env bash
set -euo pipefail
cd /workspace/MT5
python3 -m venv /workspace/mt5-venv
/workspace/mt5-venv/bin/python -m pip install -r requirements-cloud.lock
/workspace/mt5-venv/bin/python -m pip install --no-deps --no-build-isolation -e .
/workspace/mt5-venv/bin/python -m pytest -q
