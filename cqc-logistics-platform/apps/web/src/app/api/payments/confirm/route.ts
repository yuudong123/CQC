import { confirmPayment, parseConfirmBody } from "@/lib/toss-confirm";

/** 결제창 인증이 끝난 결제를 토스페이먼츠 승인 API로 확정한다(테스트 키 전용). */
export async function POST(request: Request) {
  const headers = { "Cache-Control": "no-store" };
  const body = parseConfirmBody(await request.json().catch(() => null));
  if (!body) return Response.json({ code: "INVALID_PAYMENT", message: "결제 정보 형식이 올바르지 않습니다" }, { status: 422, headers });
  const result = await confirmPayment(body);
  if (!result.ok) return Response.json({ code: result.code, message: result.message }, { status: result.status, headers });
  return Response.json(result.payment, { headers });
}
