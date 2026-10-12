import type { Confirmed, PaymentConfig } from "./toss-confirm";

/** 브라우저 쪽 토스페이먼츠 결제창(SDK v2). PC에서 iframe으로 띄우고 Promise로 결과를 받아 시연 화면을 떠나지 않는다. */
const SDK_URL = "https://js.tosspayments.com/v2/standard";
type RequestResult = { paymentKey: string; orderId: string; amount: { value: number; currency: string } };
type TossPayments = ((clientKey: string) => { payment: (options: { customerKey: string }) => { requestPayment: (request: unknown) => Promise<RequestResult> } }) & { ANONYMOUS: string };
declare global { interface Window { TossPayments?: TossPayments } }

let sdk: Promise<TossPayments> | null = null;
function loadSdk(): Promise<TossPayments> {
  if (window.TossPayments) return Promise.resolve(window.TossPayments);
  sdk ??= new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SDK_URL; script.async = true;
    script.onload = () => (window.TossPayments ? resolve(window.TossPayments) : reject(new Error("토스 결제 모듈을 불러오지 못했습니다")));
    script.onerror = () => { sdk = null; script.remove(); reject(new Error("토스 결제 모듈을 불러오지 못했습니다(인터넷 연결 확인)")); };
    document.head.appendChild(script);
  });
  return sdk;
}

export async function fetchPaymentConfig(): Promise<PaymentConfig> {
  try {
    const response = await fetch("/api/payments/config", { cache: "no-store" });
    if (!response.ok) throw new Error();
    return await response.json();
  } catch {
    return { enabled: false, clientKey: "", reason: "결제 설정을 확인하지 못했습니다" };
  }
}

/** 토스 주문번호 규칙(영문·숫자·-_=, 6–64자)에 맞춰 출품 ID로 만든다. 재시도마다 새 번호를 쓴다. */
export function paymentOrderId(lotId: string): string {
  const suffix = Array.from(crypto.getRandomValues(new Uint8Array(4)), (value) => value.toString(16).padStart(2, "0")).join("");
  return `CQC-${lotId.replace(/[^A-Za-z0-9_=-]/g, "").slice(0, 40)}-${suffix}`;
}

/** 테스트 결제창을 띄우고, 인증이 끝나면 서버 승인까지 마친 결과를 돌려준다. 사용자가 창을 닫으면 오류로 끝난다. */
export async function payWithToss(config: PaymentConfig, request: { orderId: string; orderName: string; amount: number; customerName: string }): Promise<Confirmed> {
  if (!config.enabled || !config.clientKey.startsWith("test_ck_")) throw new Error(config.reason || "테스트 결제를 쓸 수 없습니다");
  const TossPayments = await loadSdk();
  const payment = TossPayments(config.clientKey).payment({ customerKey: TossPayments.ANONYMOUS });
  const result = await payment.requestPayment({
    method: "CARD", amount: { currency: "KRW", value: request.amount },
    orderId: request.orderId, orderName: request.orderName, customerName: request.customerName,
  });
  if (result.orderId !== request.orderId || result.amount.value !== request.amount) throw new Error("결제 금액·주문번호가 요청과 다릅니다");
  const response = await fetch("/api/payments/confirm", {
    method: "POST", cache: "no-store", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paymentKey: result.paymentKey, orderId: request.orderId, amount: request.amount }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.message ?? `결제 승인 실패 (${response.status})`);
  return data as Confirmed;
}
