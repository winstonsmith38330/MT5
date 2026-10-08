param([string]$Python = 'py')
$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path "$PSScriptRoot/../..")
& $Python -3.12 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Install supported Python 3.12 first' }
& ./.venv/Scripts/python.exe -m pip install -r requirements-cloud.lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& ./.venv/Scripts/python.exe -m pip install -e '.[windows,test]'
if ($LASTEXITCODE -ne 0) { throw 'Windows dependency installation failed' }
& ./.venv/Scripts/python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Offline tests failed' }
