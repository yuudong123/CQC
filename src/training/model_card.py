"""Create the final model card from approved, immutable result artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.data.multiview import CULTIVAR_CLASSES, QUALITY_CLASSES


def failure_cases(test_result: dict[str, Any]) -> list[dict[str, Any]]:
    predictions = test_result["test"].get("predictions", [])
    return [
        row
        for row in predictions
        if row["cultivar_target_index"] != row["cultivar_prediction_index"]
        or row["quality_target_index"] != row["quality_prediction_index"]
    ]


def render_card(
    manifest: dict[str, Any],
    comparison: dict[str, Any],
    test_result: dict[str, Any],
    thresholds: dict[str, Any],
    benchmark: dict[str, Any],
) -> str:
    if test_result.get("test_used") is not True:
        raise ValueError("최종 Test 결과 파일이 아닙니다")
    test = test_result["test"]
    failures = failure_cases(test_result)
    threshold_selection = thresholds.get("selection")
    benchmark_rows = benchmark.get("results", [])
    failure_ids = ", ".join(row["group_no"] for row in failures[:10]) or "없음"
    approved = (
        test["cultivar"]["macro_f1"] >= 0.90
        and test["quality"]["macro_f1"] >= 0.90
    )
    cpu = str(benchmark.get("cpu", "unknown"))
    target_cpu_verified = "i7-4790" in cpu.lower()
    benchmark_table = "\n".join(
        "| {concurrency} | {p95_ms:.1f}ms | {throughput_per_second:.2f} | {meets_500ms} | {meets_2_per_second} |".format(
            **row
        )
        for row in benchmark_rows
    ) or "| - | - | - | - | - |"
    return f"""# CQC 모델 카드

## 식별 정보

- 모델명: `{manifest['model_name']}`
- 모델 버전: `{manifest['model_version']}`
- 체크포인트 SHA-256: `{manifest['checkpoint_sha256']}`
- 모델 구조: `{manifest['model_kind']}`
- 입력 장수: {manifest['views']}
- 입력 크기: {manifest['image_size']}×{manifest['image_size']} RGB

## 클래스 계약

- 품종: `{', '.join(CULTIVAR_CLASSES)}`
- 품질: `{', '.join(QUALITY_CLASSES)}`
- 전처리 버전: `{manifest['preprocessing_version']}`

## 평가 결과

- 5-fold 추천 상태: `{comparison.get('recommendation', {}).get('status', 'unknown')}`
- 최종 Test 표본: {test['samples']}그룹
- 품종 Accuracy: {test['cultivar']['accuracy']:.4f}
- 품종 Macro F1: {test['cultivar']['macro_f1']:.4f}
- 품질 Accuracy: {test['quality']['accuracy']:.4f}
- 품질 Macro F1: {test['quality']['macro_f1']:.4f}
- 실패 그룹 수: {len(failures)}
- 실패 그룹 예시: {failure_ids}
- 최종 Test 사용: 1회
- 승인 기준: 품종·품질 Macro F1 각각 0.90 이상
- 모델 품질 승인: {'통과' if approved else '실패'}

## 운영 설정

- 신뢰도 기준: `{json.dumps(threshold_selection, ensure_ascii=False)}`
- 측정 CPU: `{cpu}`
- 논리 CPU 수: `{benchmark.get('logical_cpu_count', 'unknown')}`
- 목표 i7-4790 수용시험: {'완료' if target_cpu_verified else '미완료'}
- inference는 예측만 담당하며 bin·재검사·DB 정책은 백엔드가 담당한다.

| 동시 처리 | p95 | 처리량/초 | 500ms | 초당 2건 |
|---:|---:|---:|---|---|
{benchmark_table}

## 한계

- 사과 부사·양광과 L/M/S 품질 외 입력은 보장하지 않는다.
- 촬영 환경과 품목 변화에 대한 일반화는 검증되지 않았다.
- 중복 해시 이미지 5쌍은 원본에서 제거하지 않았다.
- 목표 장비가 아닌 CPU 측정은 i7-4790 성능 승인 근거로 사용하지 않는다.
"""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="확정 산출물로 모델 카드 생성")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--test-result", type=Path, required=True)
    parser.add_argument("--thresholds", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    card = render_card(
        read_json(args.manifest),
        read_json(args.comparison),
        read_json(args.test_result),
        read_json(args.thresholds),
        read_json(args.benchmark),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(card, encoding="utf-8", newline="\n")
    print(f"model_card={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
