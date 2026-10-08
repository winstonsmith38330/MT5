$ErrorActionPreference = 'Stop'
Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(terminal64|terminal|metaeditor64|metaeditor)\.exe$' } | Select-Object Name, ExecutablePath
# These are candidates, not a declaration that the worker is configured.
$roots = @("$env:APPDATA/MetaQuotes/Terminal", "$env:MT5_RESEARCH_ROOT/terminal")
foreach ($root in $roots) {
    if (Test-Path $root) { Get-ChildItem -Directory $root | Select-Object FullName }
}
Write-Output 'Confirm dedicated portable data directory using MT5 File > Open Data Folder; never select an interactive installation automatically.'
