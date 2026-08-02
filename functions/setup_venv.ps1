# Creates functions\venv and installs the backend, dependencies read from
# pyproject.toml so there is exactly one dependency list.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python -m venv venv
& .\venv\Scripts\python.exe -m pip install --upgrade pip --quiet
& .\venv\Scripts\python.exe -m pip install -e ".[dev]"
Write-Host "OK - functions\venv ready. Copy config\.env.example to config\.env and fill it in."
