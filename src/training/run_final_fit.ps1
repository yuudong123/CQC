$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location -LiteralPath $repo

$outputDirectory = Join-Path $repo "outputs\final-training"
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$stdout = Join-Path $outputDirectory "final-fit.stdout.log"
$stderr = Join-Path $outputDirectory "final-fit.stderr.log"
$python = Join-Path $repo ".venv\Scripts\python.exe"

& $python -m src.training.final_fit `
    --execute `
    --device cuda `
    1>> $stdout 2>> $stderr

exit $LASTEXITCODE
