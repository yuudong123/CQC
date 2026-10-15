# ALL-04 2단계 — Jenkins #139 배포 확인 증거

2026-10-12 최종 수용시험 2단계 배포 확인 완료. 실행자 홍유나.

- Jenkins `CQC-CICD #139`: **SUCCESS**, 완료 **09:29:59.935 KST**
- checkout SHA: `b5f1995a7e4a494ef116d62819b169fa9d5a788e`
- 배포 대조 시각: **09:30:52.382 KST**
- Backend·Inference·Simulator·Frontend(`logistics-web`) 실행 이미지와 해당 빌드 digest **4/4 일치**
- Docker daemon 일치 및 `verified=true` 확인
- 기동 상태 확인 시 Compose 서비스 7개 healthy 관찰. 4개 이미지 출처의 상세 원자료는 아래 JSON에 보존.

## 증거

| 파일 | 내용 |
|---|---|
| [deployment-provenance.json](deployment-provenance.json) | checkout SHA, 빌드 번호, 서비스별 실행 이미지·빌드 digest 및 대조 결과 |
| [build-139-selected-log.txt](build-139-selected-log.txt) | checkout·이미지 digest·VERIFY SUCCESS 관련 Jenkins 로그 발췌 |
| [build-summary.json](build-summary.json) | Jenkins build.xml에서 추출한 SUCCESS·시작/완료 시각 및 10분 안정 시각 |
| [manifest.sha256](manifest.sha256) | 이 폴더의 파일별 SHA-256 |

원본 경로: `outputs/mo09-investigation-139-20261012-093050/`. JSON과 선택 로그는 원본 바이트 그대로 복사. 당시 수집 스크립트가 함께 산출한 10-06·10-07 과거 회차 timing 자료는 이번 2단계 배포 확인 증거에 포함하지 않음.

빌드 시작/완료 시각은 `build-summary.json`의 밀리초 값 보존. 기존 댓글의 09:29:59 표기는 초 단위 표기.

이 결과의 범위는 최신 배포 확인. 정상 100건 및 최종 전체 수용 판정은 별도 단계.

## 실행 및 관련 기록

```powershell
python scripts/qa/collect_mo09_followup.py --build 139 --output outputs/mo09-investigation-139-20261012-093050
```

- [최종 수용시험 #65](https://github.com/yuudong123/CQC/issues/65)
- [2단계 완료 댓글](https://github.com/yuudong123/CQC/issues/65#issuecomment-6115657793)
