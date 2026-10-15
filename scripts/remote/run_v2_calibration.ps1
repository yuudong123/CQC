# v2 후보 설정(separate·12장·Focal γ2·lr 3e-4·dropout 0.4·wd 5e-4·4 epoch)으로 5-fold를 다시 학습해
# fold별 검증 사과의 OOF logits를 만들고, temperature 보정과 재검사 임계값 표를 계산한다. Test는 쓰지 않는다.
# 원격 Windows GPU PC의 저장소 루트에서 실행한다. RTX 4070 기준 약 15~30분.
param(
    [string]$OutputRoot = "outputs\v2-calibration",
    [string]$Device = "cuda",
    [double]$MinQualityAccuracy = 0.95,
    [double]$MaxReinspection = 0.30
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location -LiteralPath $repo
$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "가상환경 Python이 없습니다: $python" }

$output = Join-Path $repo $OutputRoot
New-Item -ItemType Directory -Force -Path $output | Out-Null
$log = Join-Path $output "run.log"

foreach ($fold in 0..4) {
    $foldDir = Join-Path $output "fold-$fold"
    $last = Join-Path $foldDir "last.pt"
    if (-not (Test-Path -LiteralPath $last)) {
        & $python -m src.training.train `
            --model-kind separate --views 12 --cv-fold $fold --epochs 4 --batch-size 2 `
            --learning-rate 0.0003 --weight-decay 0.0005 --dropout 0.4 `
            --quality-loss focal --focal-gamma 2.0 --seed 42 --workers 0 `
            --device $Device --save-last --output-dir $foldDir *>> $log
        if ($LASTEXITCODE -ne 0) { throw "fold $fold 학습 실패 (로그: $log)" }
    }
    & $python -m src.training.export_predictions `
        --checkpoint $last --cv-fold $fold --device $Device `
        --output (Join-Path $output "oof-fold-$fold.csv") *>> $log
    if ($LASTEXITCODE -ne 0) { throw "fold $fold 예측 내보내기 실패 (로그: $log)" }
}

& $python -m src.training.calibration fit `
    --predictions (Join-Path $output "oof-fold-*.csv") `
    --output (Join-Path $output "calibration.json") `
    --table (Join-Path $output "threshold-table.csv") `
    --min-quality-accuracy $MinQualityAccuracy --max-reinspection $MaxReinspection *>> $log
if ($LASTEXITCODE -ne 0) { throw "보정 계산 실패 (로그: $log)" }

Get-Content -LiteralPath $log -Tail 3
Write-Output "완료: $output\calibration.json, threshold-table.csv, oof-fold-*.csv 를 노트북 C:\CQC\outputs\v2-calibration\ 로 복사하세요."
