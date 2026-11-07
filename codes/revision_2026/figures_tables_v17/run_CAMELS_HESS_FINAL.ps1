param(
    [Parameter(Mandatory=$true)][string]$ProjectRoot,
    [string]$HessOutputRoot = "",
    [switch]$BuildV17,
    [int]$Dpi = 300
)
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$V17 = Join-Path $ProjectRoot 'results\CAMELS_V17_FINAL'
if (-not $HessOutputRoot) { $HessOutputRoot = Join-Path $ProjectRoot 'results\CAMELS_HESS_FINAL' }
if ($BuildV17) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Here 'run_CAMELS_v17_FINAL.ps1') -ProjectRoot $ProjectRoot -Dpi $Dpi
    if ($LASTEXITCODE -ne 0) { throw 'V17 builder failed; HESS export aborted' }
}
if (-not (Test-Path -LiteralPath $V17)) { throw "Missing V17 figure/table output folder: $V17" }
& python.exe (Join-Path $Here 'export_hess_assets.py') --v17-root $V17 --outdir $HessOutputRoot
if ($LASTEXITCODE -ne 0) { throw 'HESS asset export failed' }
Write-Host "HESS_OUTPUT=$HessOutputRoot"
