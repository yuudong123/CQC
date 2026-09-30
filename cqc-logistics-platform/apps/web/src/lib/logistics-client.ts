import { fakeLogisticsFetch } from "./logistics-fake";

/**
 * 물류 화면 요청의 단일 진입점. 기본은 브라우저 안 가상 물류(시연용)이고,
 * 빌드 시 NEXT_PUBLIC_LOGISTICS_MODE=live이면 NEXT_PUBLIC_API_URL의 실제 물류 API를 쓴다.
 */
export const logisticsLive = process.env.NEXT_PUBLIC_LOGISTICS_MODE === "live";
export const logisticsApiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export function logisticsFetch(path: string, init: RequestInit = {}): Promise<Response> {
  return logisticsLive ? fetch(`${logisticsApiUrl}${path}`, init) : fakeLogisticsFetch(path, init);
}
