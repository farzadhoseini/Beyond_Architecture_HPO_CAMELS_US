param(
    [string]$ProjectRoot = "F:\Experiments\CAMELS_US\Clean_4_upload",
    [int]$Dpi = 300,
    [switch]$KeepBuild
)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$CoreRunner = Join-Path $Here "run_all_camels_figures_final.py"
$RevisionRunner = Join-Path $Here "revision_results_figures_v17.py"
$Assembler = Join-Path $Here "assemble_figures_v17.py"
$TableBuilder = Join-Path $Here "build_tables_v17.py"
$Validator = Join-Path $Here "validate_v17.py"
$RevisionData = Join-Path $Here "revision_data"

foreach ($Required in @($CoreRunner,$RevisionRunner,$Assembler,$TableBuilder,$Validator,$RevisionData)) {
    if (-not (Test-Path $Required)) { throw "V17 required component not found: $Required" }
}
if (-not (Test-Path $ProjectRoot)) { throw "CAMELS project root not found: $ProjectRoot" }

$BuildRoot = Join-Path $ProjectRoot "results\CAMELS_V17_BUILD"
$CoreBuild = Join-Path $BuildRoot "core"
$RevisionBuild = Join-Path $BuildRoot "revision"
$RevisionTableBuild = Join-Path $BuildRoot "revision_tables_internal"
$FinalRoot = Join-Path $ProjectRoot "results\CAMELS_V17_FINAL"
$FinalFigures = Join-Path $FinalRoot "figures"
$FinalTables = Join-Path $FinalRoot "tables"

if (Test-Path $BuildRoot) { Remove-Item -Recurse -Force $BuildRoot }
if (Test-Path $FinalRoot) { Remove-Item -Recurse -Force $FinalRoot }
New-Item -ItemType Directory -Force -Path $BuildRoot | Out-Null
New-Item -ItemType Directory -Force -Path $FinalRoot | Out-Null

$OldPythonPath=$env:PYTHONPATH
$env:PYTHONPATH=$Here
Push-Location $Here
try {
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host " CAMELS-US FINAL PAPER ASSET BUILDER - V17" -ForegroundColor Cyan
    Write-Host " 35 manuscript PDFs + 34 manuscript LaTeX tables" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "Project root : $ProjectRoot"
    Write-Host "Final root   : $FinalRoot"
    Write-Host ""

    Write-Host "[1/6] Strict source/manuscript gate..." -ForegroundColor Yellow
    python .\validate_v17.py
    if ($LASTEXITCODE -ne 0) { throw "V17 source validation failed." }

    Write-Host "[2/6] Regenerating 28 core production figures into staging..." -ForegroundColor Yellow
    python .\run_all_camels_figures_final.py `
        --project-root $ProjectRoot `
        --outdir "results/CAMELS_V17_BUILD/core" `
        --metrics NSE `
        --models "Benchmark,Cluster-wise,Top10" `
        --dpi $Dpi `
        --seed-years "1992,1998" `
        --clean-outdir
    if ($LASTEXITCODE -ne 0) { throw "V17 core figure generation failed with exit code $LASTEXITCODE" }

    Write-Host "[3/6] Regenerating 7 revision figures into staging..." -ForegroundColor Yellow
    python .\revision_results_figures_v17.py `
        --project-root $ProjectRoot `
        --revision-data-root $RevisionData `
        --figure-outdir "results/CAMELS_V17_BUILD/revision" `
        --table-outdir "results/CAMELS_V17_BUILD/revision_tables_internal"
    if ($LASTEXITCODE -ne 0) { throw "V17 revision figure generation failed with exit code $LASTEXITCODE" }

    Write-Host "[4/6] Assembling ONLY the 35 figure filenames referenced by the current manuscripts..." -ForegroundColor Yellow
    python .\assemble_figures_v17.py --core-dir $CoreBuild --revision-dir $RevisionBuild --outdir $FinalFigures
    if ($LASTEXITCODE -ne 0) { throw "V17 figure assembly failed." }

    Write-Host "[5/6] Emitting the 34 canonical LaTeX tables..." -ForegroundColor Yellow
    python .\build_tables_v17.py --outdir $FinalTables
    if ($LASTEXITCODE -ne 0) { throw "V17 table generation failed." }

    Write-Host "[6/6] Final exact-name/count gate..." -ForegroundColor Yellow
    python .\validate_v17.py --final-root $FinalRoot
    if ($LASTEXITCODE -ne 0) { throw "V17 final validation failed." }
}
finally {
    Pop-Location
    $env:PYTHONPATH=$OldPythonPath
}

if (-not $KeepBuild) {
    if (Test-Path $BuildRoot) { Remove-Item -Recurse -Force $BuildRoot }
}

$FigCount=@(Get-ChildItem $FinalFigures -Filter *.pdf -File).Count
$TabCount=@(Get-ChildItem $FinalTables -Filter *.tex -File).Count
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " V17 FINAL PAPER ASSET GATE: PASS" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Figures : $FinalFigures  ($FigCount PDFs)"
Write-Host "Tables  : $FinalTables  ($TabCount TEX files)"
Write-Host "Build staging removed: $(-not $KeepBuild)"
