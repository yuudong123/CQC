param(
    [Parameter(Mandatory = $true)]
    [string]$Checkpoint,
    [string]$OutputDirectory = "outputs\i7-4790-acceptance"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location -LiteralPath $repo

$cpuNames = @(Get-CimInstance Win32_Processor | ForEach-Object { $_.Name.Trim() })
if (-not ($cpuNames | Where-Object { $_ -match "i7-4790" })) {
    throw "Target CPU mismatch. Required: i7-4790. Detected: $($cpuNames -join ', ')"
}

$memoryBytes = [int64](Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory
if ($memoryBytes -lt 15GB) {
    throw "RAM requirement not met. Required: 16GB. Detected: $([math]::Round($memoryBytes / 1GB, 1))GB"
}

$checkpointPath = (Resolve-Path -LiteralPath $Checkpoint).Path
$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Virtual environment Python not found: $python"
}

$outputPath = Join-Path $repo $OutputDirectory
New-Item -ItemType Directory -Force -Path $outputPath | Out-Null
$latencyPath = Join-Path $outputPath "latency.json"
$concurrencyPath = Join-Path $outputPath "concurrency.json"
$acceptancePath = Join-Path $outputPath "acceptance.json"

& $python -m src.training.benchmark `
    --checkpoint $checkpointPath `
    --device cpu `
    --warmup 10 `
    --repeats 100 `
    --output $latencyPath
if ($LASTEXITCODE -ne 0) { throw "Sequential latency benchmark failed: $LASTEXITCODE" }

& $python -m src.training.benchmark_concurrency `
    --checkpoint $checkpointPath `
    --device cpu `
    --concurrency 1 2 4 `
    --repeats 100 `
    --torch-threads 1 `
    --output $concurrencyPath
if ($LASTEXITCODE -ne 0) { throw "Concurrency benchmark failed: $LASTEXITCODE" }

$latency = Get-Content -LiteralPath $latencyPath -Raw | ConvertFrom-Json
$concurrency = Get-Content -LiteralPath $concurrencyPath -Raw | ConvertFrom-Json
$sequential = @($concurrency.results | Where-Object { $_.concurrency -eq 1 })[0]
$accepted = (
    $latency.p95_ms -le 500 -and
    $sequential.p95_ms -le 500 -and
    $sequential.throughput_per_second -ge 2
)
$result = [ordered]@{
    target_cpu = "Intel Core i7-4790"
    detected_cpu = $cpuNames
    memory_gb = [math]::Round($memoryBytes / 1GB, 1)
    checkpoint = $checkpointPath
    checkpoint_sha256 = (Get-FileHash -LiteralPath $checkpointPath -Algorithm SHA256).Hash.ToLowerInvariant()
    latency = $latency
    concurrency = $concurrency
    criteria = [ordered]@{
        p95_ms_max = 500
        throughput_per_second_min = 2
        requests = 100
    }
    accepted = $accepted
}
$result | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $acceptancePath -Encoding utf8
Write-Output "acceptance=$acceptancePath accepted=$accepted"
if (-not $accepted) { exit 2 }
