# 데이터·모델 기술 스택

- 담당자: 조현재
- 작성 기한: 2026-09-17
- 상태: DM-01~DM-08 구현·비교 완료, DM-09 최종 학습·평가 진행

## 현재 확정

- 개발 기준: Python 3.11.9
- 검사 단위: 동일 `group_no`의 다각도 사과 그룹
- 정답: 부사·양광 품종과 `L=특`, `M=상`, `S=보통` 품질
- 원본 접근: ZIP을 풀지 않고 이미지·JSON 멤버를 파일명 stem으로 연결
- 매니페스트 생성: `python -m src.data.manifest`
- 전체 이미지 무결성 검사: `python -m src.data.image_quality`
- 그룹 층화 분할 생성: `python -m src.data.split_groups`
- 다각도 선택·마스킹 검증: `python -m src.data.multiview --smoke-load`
- 학습 코드 위치: `src/training/`
- 단일 학습 진입점: `python -m src.training.train --model-kind joint --views 8 --cv-fold 0`
- 전체 비교 계획 생성: `python -m src.training.experiments` (`--execute` 없이는 학습하지 않음)
- 5-fold 결과 집계: `python -m src.training.summarize ... --output outputs/summary.json`
- 전체 비교표·차트·임시 후보: `python -m src.training.report --chart`
- 승인 모델 패키징: `python -m src.training.package_model ...`
- CPU·GPU 추론시간 측정: `python -m src.training.benchmark ...`
- 최종 Test 평가: `python -m src.training.evaluate ...` (확인 문자열 필수)
- 추론 서비스: `python -m src.inference.api --model-dir models/<version>`
- 생성 위치: `data/processed/manifest.csv`, `data/processed/manifest-summary.json`
- 무결성 결과: `data/processed/image-quality-report.json`
- 모델 파일·체크포인트·생성 매니페스트는 Git에서 제외

## 최종 선택 설정

- 프레임워크: Python 3.11, PyTorch·torchvision
- 구조: 품종·품질별 MobileNetV3 Small 인코더를 둔 `separate`
- 입력: 동일 사과의 대표 12장, 224×224 RGB
- 그룹 결합: 누락 뷰를 제외한 특징 평균
- 최종 학습: Test 제외 152그룹, 19 epoch
- 신뢰도 기준: 품종 0.50, 품질 0.50
- 요청 제한: 12파일, multipart 전체 24MiB
- 모델 버전: `cqc-apple-separate12-v1.0.0`
- 운영 기본 동시 처리: 1
- 미결정: i7-4790 CPU 최종 평균·최대·p95

## DM-05 1차 기준선

- 프레임워크: PyTorch, torchvision
- 특징 추출기: ImageNet 사전학습 MobileNetV3 Small
- 그룹 결합: 실제 뷰만 포함하는 마스크 평균
- 출력: 공유 그룹 특징에서 품종 2클래스와 품질 3클래스 헤드 분기
- 입력 크기: 224×224 RGB
- 학습 증강: 수평 뒤집기와 ±8° 회전
- 평가 전처리: 리사이즈와 ImageNet 정규화만 적용
- 패딩 이미지: 0 텐서로 만들되 `view_mask=False`로 그룹 평균에서 제외

50개 5-fold 실험 비교에서 `separate/12장`이 가장 높은 두 과제 평균 Macro F1을 보여 최종 설정으로 선택했다. 목표 i7-4790 성능 승인은 해당 장비에서 별도로 완료한다.
