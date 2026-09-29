# 품질 개선용 손실함수·정규화 설정을 비교하는 v2 실험을 실행한다.
# scripts/remote 기준 두 단계 위가 저장소 루트다.
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location -LiteralPath $repo

# 실행 로그는 v2 결과 폴더에 따로 남긴다.
$outputDirectory = Join-Path $repo "outputs\training-v2"
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$stdout = Join-Path $outputDirectory "experiments.stdout.log"
$stderr = Join-Path $outputDirectory "experiments.stderr.log"
$python = Join-Path $repo ".venv\Scripts\python.exe"

# 실행 옵션을 켜므로 실험 계획 작성과 GPU 학습이 함께 시작된다.
& $python -m src.training.improvement_experiments `
    --output "outputs\training-v2-plan.json" `
    --device cuda `
    --execute `
    1>> $stdout 2>> $stderr

exit $LASTEXITCODE
