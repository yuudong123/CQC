$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location -LiteralPath $repo

$outputDirectory = Join-Path $repo "outputs\training"
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$stdout = Join-Path $outputDirectory "experiments.stdout.log"
$stderr = Join-Path $outputDirectory "experiments.stderr.log"
$python = Join-Path $repo ".venv\Scripts\python.exe"

& $python -m src.training.experiments `
    --execute `
    --device cuda `
    --output "outputs\training-plan.json" `
    1>> $stdout 2>> $stderr

exit $LASTEXITCODE
