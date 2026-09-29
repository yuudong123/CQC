# 프론트엔드 기술 스택 및 구현 상태

확인일: 2026-09-29 · 담당: 강성민 · 구현: `cqc-logistics-platform/apps/web`

## 기준 문서

- [전체 작업 요약](../../Frontend-작업-종합정리.md): 화면 변경, FE-01~09, 검증·잔여·코드 위치.
- [관제 API 인계](../../협업공지/Frontend-관제-API-계약-인계.md): 실행법·API·협업 요청.
- [OpenAPI](../../../contracts/quality-operations.openapi.json): 상세 요청·응답 schema.

## 기술 구성

Next.js 16.3.5, React 19.2.8, TypeScript 5, CSS Grid, native dialog. 품질 페이지는 전체 배율 축소 없이 화면 크기에 맞추고 내부 목록만 스크롤한다. 공통 헤더는 입찰·차량 페이지에만 표시한다.

화면 → useQualityConnection → 동일출처 proxy → 관제 API로 연결한다. 브라우저 demo와 API mode를 구분하며, API의 source는 reference/backend로 구분한다. 실패 시 demo로 자동 전환하지 않는다.

서버 응답 검증, 순차 polling·취소·시간 제한, 제어 revision 충돌, 관리 목록 시점 고정, 서버 전체 CSV를 구현했다. 참조 서버는 별도 Node 프로세스의 메모리 상태이며 실제 모델·DB와 다르다.

## 완료 판정

FE-01~07 클라이언트와 참조 API를 구현했다. 자동 시험 20개와 lint/build 통과 기록이 있다. 실제 Backend/Simulator/DB 통합, 실제 장시간 브라우저 검증, 공동 수용시험·동결은 남아 있다. 상세 상태는 전체 작업 요약을 따른다.
