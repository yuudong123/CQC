/**
 * CQC 웹: 품질 관제(`/`), 입찰 시장(`/market`), 차량 관제(`/control`).
 *
 * 실행: `npm ci` → `npm run dev` (http://localhost:3000). 확인: `npm test`, `npm run lint`, `npm run build`.
 * 물류 API 주소는 `NEXT_PUBLIC_API_URL`(기본 http://localhost:8000/api/v1), 지도 키는
 * `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`로 빌드 시 넣는다. 품질 관제는 기본 브라우저 데모이며
 * `CQC_QUALITY_MODE=api`, `CQC_QUALITY_BACKEND_URL`로 QC Backend 관제 API를 호출한다.
 *
 * 화면 데이터 주의: 품질 화면 사진은 AI Hub 시연 묶음(출처 `public/apples/provenance.json`)이고
 * 데모 모드의 판정·가상 당도는 예시 값이다. 출품 사진은 같은 품종·등급의 참고 이미지다.
 * 구매자/관리자 전환은 시연용 UI이며 인증 기능이 아니다. 관제의 "발표 상태 초기화"는 로컬 메모리
 * API의 데모 출품·차량을 다시 만든다. 작업 기록은 docs/wbs/FE-01~10, docs/wbs/LOGISTICS.md.
 */
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
};

export default nextConfig;
