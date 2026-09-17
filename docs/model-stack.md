# 데이터·모델 기술 스택

- 담당자: 조현재
- 작성 기한: 2026-09-17
- 상태: DM-01~DM-04 완료, DM-05 MobileNetV3 Small 그룹 기준선 구현 중

## 현재 확정

- 개발 기준: Python 3.11.9
- 검사 단위: 동일 `group_no`의 다각도 사과 그룹
- 정답: 부사·양광 품종과 `L=특`, `M=상`, `S=보통` 품질
- 원본 접근: ZIP을 풀지 않고 이미지·JSON 멤버를 파일명 stem으로 연결
- 매니페스트 생성: `python -m src.data.manifest`
- 전체 이미지 무결성 검사: `python -m src.data.image_quality`
- 그룹 층화 분할 생성: `python -m src.data.split_groups`
- 다각도 선택·마스킹 검증: `python -m src.data.multiview --smoke-load`
- 생성 위치: `data/processed/manifest.csv`, `data/processed/manifest-summary.json`
- 무결성 결과: `data/processed/image-quality-report.json`
- 모델 파일·체크포인트·생성 매니페스트는 Git에서 제외

## 다음 확정 항목

- 학습 프레임워크와 버전
- 이미지 특징 추출 모델 후보
- 그룹 결합 방식
- 단일 모델·분리 모델 구조
- 입력 해상도와 4·8·12·16·40장 비교 방법
- 전처리·증강·누락 뷰 마스킹
- CPU 추론 최적화 방식
- 모델 파일 형식과 버전 규칙
- 실행·학습·평가 명령
- 선택 근거와 미결정 사항

## DM-05 1차 기준선

- 프레임워크: PyTorch, torchvision
- 특징 추출기: ImageNet 사전학습 MobileNetV3 Small
- 그룹 결합: 실제 뷰만 포함하는 마스크 평균
- 출력: 공유 그룹 특징에서 품종 2클래스와 품질 3클래스 헤드 분기
- 입력 크기: 224×224 RGB
- 학습 증강: 수평 뒤집기와 ±8° 회전
- 평가 전처리: 리사이즈와 ImageNet 정규화만 적용
- 패딩 이미지: 0 텐서로 만들되 `view_mask=False`로 그룹 평균에서 제외

MobileNetV3 Small은 첫 기준선이며 최종 승인 모델이 아니다. 입력 장수와 더 큰 모델 비교는 DM-06에서 수행한다.

결정하지 않은 항목은 임의로 확정하지 말고 후보, 비교 방법과 결정 시점을 적는다.
