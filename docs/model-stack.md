# 데이터·모델 기술 스택

- 담당자: 조현재
- 작성 기한: 2026-09-17
- 상태: DM-01~DM-03 완료, 리뷰 후 DM-04 다각도 로더 착수 가능

## 현재 확정

- 개발 기준: Python 3.11.9
- 검사 단위: 동일 `group_no`의 다각도 사과 그룹
- 정답: 부사·양광 품종과 `L=특`, `M=상`, `S=보통` 품질
- 원본 접근: ZIP을 풀지 않고 이미지·JSON 멤버를 파일명 stem으로 연결
- 매니페스트 생성: `python -m src.data.manifest`
- 전체 이미지 무결성 검사: `python -m src.data.image_quality`
- 그룹 층화 분할 생성: `python -m src.data.split_groups`
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

결정하지 않은 항목은 임의로 확정하지 말고 후보, 비교 방법과 결정 시점을 적는다.
