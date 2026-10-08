param([Parameter(Mandatory=$true)][string]$Workspace, [switch]$Mock)
$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path "$PSScriptRoot/../..")
$argsList = @('--workspace', (Resolve-Path $Workspace).Path, 'gateway')
if ($Mock) { $argsList += '--mock' }
& ./.venv/Scripts/python.exe -m mt5_research.cli @argsList
exit $LASTEXITCODE
