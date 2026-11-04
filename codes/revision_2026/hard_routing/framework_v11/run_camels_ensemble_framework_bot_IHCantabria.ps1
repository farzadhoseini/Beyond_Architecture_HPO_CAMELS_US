
# CAMELS Ensemble Framework Bot - IHCantabria v11 LEGACY FORMAT + F4 XLSX SLOTMAP
$ErrorActionPreference = "Stop"

# Path-locked IHCantabria project roots
$Root = "F:\Experiments\CAMELS_US\Clean_4_upload"
$RevisionRoot = Join-Path $Root "Revision_2026_Top18_4Framework"
$WorkRoot = Join-Path $RevisionRoot "ensemble_framework_bot_runs"
$PickleDir = Join-Path $Root "Pickles"
$ClustersFile = Join-Path $Root "camels_531_master_attributes_clusters.csv"
$Top18RunDir = Join-Path $RevisionRoot "runs\top18_additional8_selected_epoch_train_v57"

# Optional explicit mapping. The launcher tries to find it automatically; set here if needed.
$SelectedClusterwiseCsv = ""

# Top18 stays held until the 8 additional models are finished/exported.
$IncludeTop18 = $false

# Validation settings
$StrictRebuildCheck = $false   # set true after first diagnostic run if you want the bot to stop on mismatch
$SkipPeakMetrics = $false
$SaveEnsembles = $true

New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
$LaunchAudit = Join-Path $WorkRoot "launcher_audit"
New-Item -ItemType Directory -Force -Path $LaunchAudit | Out-Null
$LaunchLog = Join-Path $LaunchAudit ("launcher_v11_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".log")

function Log($m) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | $m"
    Write-Host $line
    Add-Content -Path $LaunchLog -Value $line
}

Log "Starting CAMELS v11 legacy-format + F4 XLSX slot-map launcher"
Log "Root: $Root"
Log "RevisionRoot: $RevisionRoot"
Log "WorkRoot: $WorkRoot"
Log "PickleDir: $PickleDir"
Log "ClustersFile: $ClustersFile"
Log "Top18RunDir: $Top18RunDir"
Log "IncludeTop18: $IncludeTop18"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ClusterConfigsXlsx = Join-Path $ScriptDir "Clusters&Configs.xlsx"
Log "ClusterConfigsXlsx: $ClusterConfigsXlsx"
$PyScript = Join-Path $ScriptDir "camels_ensemble_framework_bot.py"
$Args = @(
    $PyScript,
    "--work-root", $WorkRoot,
    "--pickle-dir", $PickleDir,
    "--clusters", $ClustersFile,
    "--revision-root", $RevisionRoot,
    "--top18-run-dir", $Top18RunDir,
    "--save-ensembles"
)
if ($SelectedClusterwiseCsv -and (Test-Path $SelectedClusterwiseCsv)) { $Args += @("--selected-clusterwise-csv", $SelectedClusterwiseCsv) }
if ($ClusterConfigsXlsx -and (Test-Path $ClusterConfigsXlsx)) { $Args += @("--cluster-configs-xlsx", $ClusterConfigsXlsx) }
if ($IncludeTop18) { $Args += "--include-top18" }
if ($StrictRebuildCheck) { $Args += "--strict-rebuild-check" }
if ($SkipPeakMetrics) { $Args += "--skip-peak-metrics" }

Log "Python command: python $($Args -join ' ')"
try { (Get-Process -Id $PID).PriorityClass = 'BelowNormal'; Log "Set launcher priority to BelowNormal" } catch {}
python @Args 2>&1 | Tee-Object -FilePath $LaunchLog -Append
$code = $LASTEXITCODE
Log "Python exit code: $code"
if ($code -ne 0) { throw "CAMELS v11 F4 XLSX slot-map bot failed. Check log: $LaunchLog" }
Log "Finished successfully"
