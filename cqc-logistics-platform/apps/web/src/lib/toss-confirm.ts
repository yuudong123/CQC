/**
 * 토스페이먼츠 결제 승인(서버 전용). 이 시연은 테스트 키만 허용해 실제 돈이 오가지 않는다.
 * 키는 TOSS_CLIENT_KEY·TOSS_SECRET_KEY 환경변수로 바꿀 수 있고, 비우면 토스 공식 샘플
 * (github.com/tosspayments/tosspayments-sample)에 공개된 문서용 테스트 키를 쓴다.
 */
const DOCS_TEST_CLIENT_KEY = "test_ck_D5GePWvyJnrK0W0k6q8gLzN97Eoq";
const DOCS_TEST_SECRET_KEY = "test_sk_zXLkKEypNArWmo50nX3lmeaxYG5R";
const CONFIRM_URL = "https://api.tosspayments.com/v1/payments/confirm";

export type PaymentConfig = { enabled: boolean; clientKey: string; reason: string };
export type ConfirmBody = { paymentKey: string; orderId: string; amount: number };
export type Confirmed = { orderId: string; status: string; method: string | null; totalAmount: number; approvedAt: string | null; receiptUrl: string | null };

type Env = Record<string, string | undefined>;

function keys(env: Env) {
  return { clientKey: env.TOSS_CLIENT_KEY || DOCS_TEST_CLIENT_KEY, secretKey: env.TOSS_SECRET_KEY || DOCS_TEST_SECRET_KEY };
}

/** 라이브 키가 들어오면 결제를 끄고 가상 결제로만 진행한다. CQC_PAYMENT_MODE=virtual이면 항상 가상 결제다. */
export function paymentConfig(env: Env = process.env): PaymentConfig {
  const { clientKey, secretKey } = keys(env);
  if (env.CQC_PAYMENT_MODE === "virtual") return { enabled: false, clientKey: "", reason: "가상 결제 모드" };
  if (!clientKey.startsWith("test_ck_") || !secretKey.startsWith("test_sk_"))
    return { enabled: false, clientKey: "", reason: "테스트 키가 아니라서 PG 결제를 껐습니다" };
  return { enabled: true, clientKey, reason: "" };
}

/** 주문번호는 CQC-로 시작하는 토스 규칙(영문·숫자·-_=, 6–64자), 금액은 시연 범위의 원 단위 정수만 받는다. */
export function parseConfirmBody(value: unknown): ConfirmBody | null {
  if (!value || typeof value !== "object") return null;
  const { paymentKey, orderId, amount } = value as Record<string, unknown>;
  if (typeof paymentKey !== "string" || paymentKey.length < 1 || paymentKey.length > 200) return null;
  if (typeof orderId !== "string" || !/^CQC-[A-Za-z0-9_=-]{2,60}$/.test(orderId)) return null;
  if (typeof amount !== "number" || !Number.isInteger(amount) || amount < 1000 || amount > 10_000_000) return null;
  return { paymentKey, orderId, amount };
}

export async function confirmPayment(body: ConfirmBody, env: Env = process.env, fetcher: typeof fetch = fetch): Promise<{ ok: true; payment: Confirmed } | { ok: false; status: number; code: string; message: string }> {
  const config = paymentConfig(env);
  if (!config.enabled) return { ok: false, status: 503, code: "PAYMENT_DISABLED", message: config.reason };
  const { secretKey } = keys(env);
  let response: Response;
  try {
    response = await fetcher(CONFIRM_URL, {
      method: "POST", cache: "no-store",
      headers: { Authorization: `Basic ${Buffer.from(`${secretKey}:`).toString("base64")}`, "Content-Type": "application/json" },
      body: JSON.stringify(body), signal: AbortSignal.timeout(10_000),
    });
  } catch {
    return { ok: false, status: 502, code: "PG_UNREACHABLE", message: "토스페이먼츠 서버에 연결하지 못했습니다" };
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) return { ok: false, status: 400, code: String(data.code ?? "PG_ERROR"), message: String(data.message ?? `결제 승인 실패 (${response.status})`) };
  return {
    ok: true,
    payment: { orderId: data.orderId, status: data.status, method: data.method ?? null, totalAmount: data.totalAmount, approvedAt: data.approvedAt ?? null, receiptUrl: data.receipt?.url ?? null },
  };
}
