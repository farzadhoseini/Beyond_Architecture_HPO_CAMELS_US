param(
    [string]$Root = "F:\Experiments\CAMELS_US\Clean_4_upload",
    [string]$DataDir = "auto",
    [string]$Out = ""
)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Here

Write-Host "============================================================"
Write-Host " CAMELS-US HI17 CONSTITUENT DECOMPOSITION - 10-SEED PROTOCOL"
Write-Host " All archived final realizations; no training; no imputation"
Write-Host "============================================================"
Write-Host "Root    : $Root"
Write-Host "DataDir : $DataDir"

$ArgsList = @(
    ".\camels_hi17_constituent_decomposition_v2.py",
    "--root", $Root,
    "--data-dir", $DataDir
)
if ($Out -ne "") {
    $ArgsList += @("--out", $Out)
}

python @ArgsList
if ($LASTEXITCODE -ne 0) {
    throw "HI17 10-seed constituent decomposition STOPPED. See FAILED.txt in the output folder."
}

$DefaultOut = Join-Path $Root "Revision_2026_Top18_4Framework\HI17_CONSTITUENT_DECOMPOSITION_10SEED_FINAL"
$ShowOut = if ($Out -ne "") { $Out } else { $DefaultOut }
Write-Host ""
Write-Host "============================================================"
Write-Host " FINAL HI17 10-SEED CONSTITUENT DECOMPOSITION: PASS"
Write-Host "============================================================"
Write-Host "Send these files to ChatGPT:"
Write-Host "  $(Join-Path $ShowOut 'MANUSCRIPT_READY.txt')"
Write-Host "  $(Join-Path $ShowOut '07_pooledHI_vs_each_constituent_core_stats.csv')"
Write-Host "  $(Join-Path $ShowOut '08_each_constituent_vs_kratzert_context.csv')"
Write-Host "  $(Join-Path $ShowOut 'RUN_SUMMARY.json')"
Write-Host "  $(Join-Path $ShowOut '03_hi17_constituent_identity.csv')"
Write-Host "  $(Join-Path $ShowOut '11_seedwise_pooledHI_vs_constituents_NSE.csv')"
