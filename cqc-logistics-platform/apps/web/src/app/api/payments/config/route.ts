import { paymentConfig } from "@/lib/toss-confirm";

/** 브라우저에 PG 사용 여부와 테스트 클라이언트 키만 알려 준다(시크릿 키는 서버에만 둔다). */
export async function GET() {
  return Response.json(paymentConfig(), { headers: { "Cache-Control": "no-store" } });
}
