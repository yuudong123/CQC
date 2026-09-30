# 기본 모델·사진 수별 비교 학습을 원격 GPU 환경에서 실행한다.
# 원격 Windows GPU PC에서 직접 또는 예약 작업으로 실행하며 실제 학습·측정을 시작한다. 예약 작업에 예전 src/training/*.ps1 경로가 남아 있으면 scripts/remote/*.ps1로 바꾼다.
# scripts/remote 기준 두 단계 위가 저장소 루트다.
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location -LiteralPath $repo

# 일반 출력과 오류 로그를 따로 남겨 원격 실행 결과를 확인한다.
$outputDirectory = Join-Path $repo "outputs\training"
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$stdout = Join-Path $outputDirectory "experiments.stdout.log"
$stderr = Join-Path $outputDirectory "experiments.stderr.log"
$python = Join-Path $repo ".venv\Scripts\python.exe"

# 실행 옵션이 있으므로 계획 작성 후 실제 학습까지 진행한다.
& $python -m src.training.experiments `
    --execute `
    --device cuda `
    --output "outputs\training-plan.json" `
    1>> $stdout 2>> $stderr

exit $LASTEXITCODE
