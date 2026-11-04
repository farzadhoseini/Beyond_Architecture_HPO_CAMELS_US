param(
    [string]$Root = "F:\Experiments\CAMELS_US\Clean_4_upload"
)
$ErrorActionPreference = "Stop"
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " CAMELS-US TOP-10 CONSTITUENT DECOMPOSITION"
Write-Host " No training; no test-based selection; Rank-1 not required"
Write-Host "============================================================" -ForegroundColor Cyan
$Script = Join-Path $PSScriptRoot "camels_top10_constituent_decomposition_v1.py"
$Out = Join-Path $Root "Revision_2026_Top18_4Framework\TOP10_CONSTITUENT_DECOMPOSITION_FINAL"
Write-Host "Root : $Root"
Write-Host "Out  : $Out"
python $Script --root $Root --out $Out
if ($LASTEXITCODE -ne 0) {
    Write-Host "CONSTITUENT DECOMPOSITION STOPPED SAFELY." -ForegroundColor Red
    Write-Host "Send the PowerShell output and $Out\FAILED.txt to ChatGPT."
    exit $LASTEXITCODE
}
Write-Host "" 
Write-Host "FINAL CONSTITUENT DECOMPOSITION: PASS" -ForegroundColor Green
Write-Host "Send these files to ChatGPT:"
Write-Host "  $Out\MANUSCRIPT_READY.txt"
Write-Host "  $Out\08_top10_vs_each_constituent_core_stats.csv"
Write-Host "  $Out\09_each_constituent_vs_kratzert_core_stats.csv"
Write-Host "  $Out\RUN_SUMMARY.json"
Write-Host "  $Out\03_unique_scientific_configurations.csv"
