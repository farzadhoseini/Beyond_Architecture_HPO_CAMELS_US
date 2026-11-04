$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectHome  = "F:\Experiments\CAMELS_US"
$Root         = Join-Path $ProjectHome "Clean_4_upload"
$RevisionRoot = Join-Path $Root "Revision_2026_Top18_4Framework"
$WorkRoot     = Join-Path $RevisionRoot "ensemble_framework_bot_runs"
$PickleDir    = Join-Path $Root "Pickles"
$ClustersFile = Join-Path $Root "camels_531_master_attributes_clusters.csv"
$ClusterConfigsXlsx = Join-Path $ScriptDir "Clusters&Configs.xlsx"
$PythonExe = "python"

Write-Host "============================================================"
Write-Host "CAMELS F4-only v13 - cluster-local Top3 own-cluster"
Write-Host "============================================================"
Write-Host "Root              : $Root"
Write-Host "WorkRoot          : $WorkRoot"
Write-Host "PickleDir         : $PickleDir"
Write-Host "ClustersFile      : $ClustersFile"
Write-Host "ClusterConfigsXlsx: $ClusterConfigsXlsx"

$ArgsList = @(
    (Join-Path $ScriptDir "camels_f4_only_bot.py"),
    "--root", $Root,
    "--work-root", $WorkRoot,
    "--pickle-dir", $PickleDir,
    "--clusters", $ClustersFile,
    "--cluster-configs-xlsx", $ClusterConfigsXlsx,
    "--save-ensembles"
)

Write-Host "Python command: $PythonExe $($ArgsList -join ' ')"
& $PythonExe @ArgsList
$ExitCode = $LASTEXITCODE
Write-Host "Python exit code: $ExitCode"
if ($ExitCode -ne 0) {
    throw "CAMELS F4-only bot failed."
}
Write-Host "Finished successfully"
