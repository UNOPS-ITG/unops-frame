#!/usr/bin/env sh
# Creates functions/venv and installs the backend, dependencies read from
# pyproject.toml so there is exactly one dependency list.
set -e
cd "$(dirname "$0")"
python3 -m venv venv 2>/dev/null || python -m venv venv
./venv/bin/python -m pip install --upgrade pip --quiet
./venv/bin/python -m pip install -e ".[dev]"
echo "✓ functions/venv ready. Copy config/.env.example to config/.env and fill it in."
