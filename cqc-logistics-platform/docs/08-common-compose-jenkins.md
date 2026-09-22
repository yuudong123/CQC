# 공통 Compose·Jenkins 배포 전환

## 목적

물류 데모를 GPU 학습용 또는 개인 홈 서버에서 분리하고, CQC의 다른 실행 단위와 동일한 저장소 루트 `compose.yaml` 및 `Jenkinsfile`로 관리한다.

## 서비스 구성

| 서비스 | 역할 | 외부 포트 | GPU |
|---|---|---:|---|
| `logistics-mongodb` | 경매·주문·차량·노선 저장 | 공개하지 않음 | 미사용 |
| `logistics-api` | FastAPI 경매·배차·관제 API | `8100` | 미사용 |
| `logistics-web` | Next.js 입찰·관제 화면 | `3100` | 미사용 |

MongoDB 데이터는 `logistics_mongodb_data` 볼륨에 보존한다. 세 서비스 모두 `restart: unless-stopped`를 사용하며, MongoDB → API → Web 순서로 healthcheck를 통과한 뒤 기동한다.

## Jenkins 처리 범위

기존 파이프라인 명령을 그대로 사용한다.

1. `docker-compose config`로 통합 설정 검사
2. `docker-compose build`에서 물류 API와 Web 이미지 빌드
3. `docker-compose up -d --no-build`로 기존 CQC 서비스와 함께 배포
4. Verify 단계에서 물류 MongoDB, API, Web의 health 상태 검사

## 배포 환경변수

- `LOGISTICS_WEB_PORT`: 기본값 `3100`
- `LOGISTICS_API_PORT`: 기본값 `8100`
- `LOGISTICS_PUBLIC_WEB_ORIGIN`: 브라우저가 접속할 Web 주소
- `LOGISTICS_PUBLIC_API_URL`: Web 빌드에 포함될 외부 API 주소
- `GOOGLE_MAPS_API_KEY`: Jenkins Credentials 또는 Job 환경변수로 주입

공개 주소 두 개는 Jenkins 배포 호스트의 실제 IP 또는 도메인으로 설정해야 한다. 지도 키는 저장소와 이미지 소스에 직접 기록하지 않는다.

## 이전 배포 종료 순서

1. 공통 Jenkins 배포 성공
2. `http://배포호스트:3100`, `http://배포호스트:8100/api/v1/health` 확인
3. 경매·관제 화면 스모크 테스트
4. 기존 개인 서버의 물류 Compose만 종료

새 배포 검증 전에는 기존 인스턴스를 먼저 종료하지 않는다.
