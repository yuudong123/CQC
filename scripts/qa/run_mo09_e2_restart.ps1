param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^cqc-mo09-e2-[a-z0-9-]+$')]
    [string]$Project,
    [Parameter(Mandatory = $true)]
    [string]$Output,
    [Parameter(Mandatory = $true)]
    [string]$Provenance
)

$ErrorActionPreference = 'Stop'
$qaRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location -LiteralPath $qaRoot
$qaBranch = (git branch --show-current).Trim()
if ($qaBranch -ne 'feat/mlops') { throw "Expected feat/mlops; actual branch: $qaBranch" }
$qaExisting = @(docker ps -aq --filter "label=com.docker.compose.project=$Project")
if ($qaExisting.Count -ne 0) { throw 'Project already has containers; choose a new project name' }
if (Test-Path -LiteralPath $Output) { throw 'Output already exists; choose a new run directory' }
$qaProof = Get-Content -LiteralPath $Provenance -Raw | ConvertFrom-Json
if (-not $qaProof.verified) { throw 'Verified image provenance required' }

$qaImages = @{}
foreach ($qaService in @('backend', 'inference', 'simulator')) {
    $qaExpected = ($qaProof.services | Where-Object service -eq $qaService).image_id
    $qaActual = (docker image inspect --format '{{.Id}}' "cqc-cicd-${qaService}:latest").Trim()
    if ($LASTEXITCODE -ne 0 -or $qaActual -ne $qaExpected) { throw "Image provenance mismatch: $qaService" }
    $qaImages[$qaService] = $qaActual
}
$qaImages['mysql'] = (docker image inspect --format '{{.Id}}' mysql:8.4).Trim()
if ($LASTEXITCODE -ne 0) { throw 'MySQL image unavailable' }
New-Item -ItemType Directory -Path $Output | Out-Null
$qaOutputPath = (Resolve-Path -LiteralPath $Output).Path
$qaPinnedCompose = Join-Path $qaOutputPath 'compose.pinned.yaml'
$qaPinnedText = @('services:')
foreach ($qaService in @('mysql', 'inference', 'backend', 'simulator')) {
    $qaPinnedText += "  ${qaService}:"
    $qaPinnedText += "    image: $($qaImages[$qaService])"
}
$qaPinnedText | Set-Content -LiteralPath $qaPinnedCompose -Encoding utf8

$qaEnvironment = @{
    MYSQL_ROOT_PASSWORD = [guid]::NewGuid().ToString('N')
    MYSQL_DATABASE = 'cqc'
    MYSQL_USER = 'cqc'
    MYSQL_PASSWORD = [guid]::NewGuid().ToString('N')
    SIMULATOR_FAULT_TOKEN = [guid]::NewGuid().ToString('N')
    BACKEND_PORT = '127.0.0.1:18000'
    INFERENCE_PORT = '127.0.0.1:18001'
    INFERENCE_CLIENT_MODE = 'http'
    INFERENCE_URL = 'http://inference:8001/v1/predict'
    SIMULATOR_INTERVAL_MS = '2000'
    CULTIVAR_CONFIDENCE_THRESHOLD = '0.50'
    QUALITY_CONFIDENCE_THRESHOLD = '0.60'
    PYTHONIOENCODING = 'utf-8'
}
$qaEnvironment['DATABASE_URL'] = "mysql+pymysql://cqc:$($qaEnvironment['MYSQL_PASSWORD'])@mysql:3306/cqc"
$qaSavedEnvironment = @{}
foreach ($qaKey in $qaEnvironment.Keys) {
    $qaSavedEnvironment[$qaKey] = [Environment]::GetEnvironmentVariable($qaKey, 'Process')
    [Environment]::SetEnvironmentVariable($qaKey, $qaEnvironment[$qaKey], 'Process')
}
$qaCompose = @('-p', $Project, '-f', 'compose.yaml', '-f', 'scripts/qa/compose.mo09.yaml', '-f', $qaPinnedCompose)
$qaExitCode = 2
try {
    docker compose @qaCompose up -d --no-build --pull never --wait --wait-timeout 600 mysql inference backend simulator 2>&1 |
        Tee-Object -FilePath (Join-Path $qaOutputPath 'startup-log.txt')
    if ($LASTEXITCODE -ne 0) { throw 'E2 startup failed' }
    python scripts/qa/run_mo09_e2_restart.py --project $Project --output $qaOutputPath --provenance $Provenance 2>&1 |
        Tee-Object -FilePath (Join-Path $qaOutputPath 'runner-log.txt')
    $qaExitCode = $LASTEXITCODE
}
catch {
    $_.Exception.Message | Tee-Object -FilePath (Join-Path $qaOutputPath 'environment-error.txt')
    $qaExitCode = 2
}
finally {
    try {
        docker compose @qaCompose down -v 2>&1 | Tee-Object -FilePath (Join-Path $qaOutputPath 'cleanup-log.txt')
        $qaCleanupCode = $LASTEXITCODE
        $qaRemaining = @(docker ps -aq --filter "label=com.docker.compose.project=$Project")
        $qaRemainingVolumes = @(docker volume ls -q --filter "label=com.docker.compose.project=$Project")
        @{ project = $Project; cleanup_exit_code = $qaCleanupCode;
           remaining_containers = $qaRemaining; remaining_volumes = $qaRemainingVolumes } |
            ConvertTo-Json | Set-Content -LiteralPath (Join-Path $qaOutputPath 'cleanup.json') -Encoding utf8
        if ($qaCleanupCode -ne 0 -or $qaRemaining.Count -ne 0 -or $qaRemainingVolumes.Count -ne 0) { $qaExitCode = 2 }
    }
    finally {
        foreach ($qaKey in $qaSavedEnvironment.Keys) {
            [Environment]::SetEnvironmentVariable($qaKey, $qaSavedEnvironment[$qaKey], 'Process')
        }
    }
}
exit $qaExitCode
