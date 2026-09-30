# 시험 사과를 제외한 개발 데이터 전체로 최종 모델을 학습한다.
# 원격 Windows GPU PC에서 직접 또는 예약 작업으로 실행하며 실제 학습·측정을 시작한다. 예약 작업에 예전 src/training/*.ps1 경로가 남아 있으면 scripts/remote/*.ps1로 바꾼다.
# scripts/remote 기준 두 단계 위에서 프로젝트 가상환경을 사용한다.
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location -LiteralPath $repo

# 원격 학습의 진행 출력과 오류를 분리해 보존한다.
$outputDirectory = Join-Path $repo "outputs\final-training"
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$stdout = Join-Path $outputDirectory "final-fit.stdout.log"
$stderr = Join-Path $outputDirectory "final-fit.stderr.log"
$python = Join-Path $repo ".venv\Scripts\python.exe"

# 학습 회차 선택과 시험 데이터 제외는 공통 최종 학습 모듈에서 처리한다.
& $python -m src.training.final_fit `
    --execute `
    --device cuda `
    1>> $stdout 2>> $stderr

exit $LASTEXITCODE
