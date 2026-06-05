$ErrorActionPreference = "Stop"

$jobRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$trainResultPath = Join-Path $jobRoot "results\train_result.json"
$modelsRoot = Join-Path $jobRoot "models"
$latestPath = Join-Path $modelsRoot "latest"

if (-not (Test-Path $trainResultPath)) {
    throw "Train result not found: $trainResultPath"
}

$trainResult = Get-Content -Path $trainResultPath -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $trainResult.ok) {
    throw "Train result is not ok. Check $trainResultPath"
}

$modelId = $trainResult.result.model_id
if ([string]::IsNullOrWhiteSpace($modelId)) {
    throw "model_id is missing from $trainResultPath"
}

$sourcePath = Join-Path $modelsRoot $modelId
if (-not (Test-Path $sourcePath)) {
    throw "Trained model directory not found: $sourcePath"
}

if (Test-Path $latestPath) {
    Remove-Item -LiteralPath $latestPath -Recurse -Force
}

Copy-Item -LiteralPath $sourcePath -Destination $latestPath -Recurse
Write-Host "Prepared latest model: $latestPath"
