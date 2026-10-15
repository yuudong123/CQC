"use client";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { useQualityConnection } from "./useQualityConnection";
import { advanceTask, collectBatches, DEMO_AUCTION_MS, DEMO_LOT_LIMIT, DEMO_LOT_SIZE, type DemoPayment, type DemoTask } from "@/lib/auction-demo";
import { fetchPaymentConfig, payWithToss, paymentOrderId } from "@/lib/toss-payment";
import type { Confirmed, PaymentConfig } from "@/lib/toss-confirm";
import type { Result } from "@/lib/quality-runtime";
import { logisticsFetch } from "@/lib/logistics-client";
type Demo = { connection: ReturnType<typeof useQualityConnection>; enabled: boolean; count: number; buffered: number; events: string[]; error: string; payment: DemoPayment | null; toggle: () => void; markPaid: (lotId: string, message: string) => void; closePayment: () => void };
// 자동 시연 한 단계를 진행하는 주기. 출품·입찰·마감이 눈에 보이되 기다리지 않을 만큼 짧게 둔다.
const DEMO_TICK_MS = 700;
const Context = createContext<Demo | null>(null);
export function useDemo() {
  const value = useContext(Context);
  if (!value) throw new Error("시연 상태 제공자가 없습니다.");
  return value;
}
/** 공통 레이아웃에 두어 페이지 이동 중에도 검사가 이어집니다. 새로고침 시 자동 동작은 꺼집니다. */
export default function DemoProvider({ mode, children }: { mode: "demo" | "api"; children: ReactNode }) {
  const connection = useQualityConnection(mode);
  const records = useRef<Result[]>([]);
  const seen = useRef(new Set<string>());
  const buckets = useRef(new Map<string, Result[]>());
  const tasks = useRef<DemoTask[]>([]);
  const session = useRef("");
  const busy = useRef(false);
  const [enabled, setEnabled] = useState(false);
  const [count, setCount] = useState(0);
  const [buffered, setBuffered] = useState(0);
  const [events, setEvents] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [payment, setPayment] = useState<DemoPayment | null>(null);
  // 결제창(토스 테스트)은 시연마다 첫 낙찰 1건만 띄우고, 나머지 낙찰은 가상 결제로 바로 넘긴다.
  const checkoutLot = useRef("");
  useEffect(() => { records.current = connection.state.history; }, [connection.state.history]);
  function toggle() {
    if (!enabled && !session.current) {
      // 내부망 HTTP에서도 사용 가능한 난수 API로 시연 실행을 구분합니다.
      session.current = Array.from(crypto.getRandomValues(new Uint8Array(16)), (value) => value.toString(16).padStart(2, "0")).join("");
      seen.current = new Set(records.current.map((row) => row.id));
    }
    setError(""); setEnabled(!enabled);
  }
  useEffect(() => {
    if (!enabled) return;
    let disposed = false;
    const controller = new AbortController();
    async function api<T>(path: string, body?: unknown): Promise<T> {
      const response = await logisticsFetch(path, {
        method: body === undefined ? "GET" : "POST", cache: "no-store", headers: { "Content-Type": "application/json" },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
        signal: AbortSignal.any([controller.signal, AbortSignal.timeout(8000)]),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `요청 실패 (${response.status})`);
      return data as T;
    }
    async function tick() {
      if (busy.current || disposed) return;
      busy.current = true;
      try {
        if (tasks.current.length < DEMO_LOT_LIMIT) {
          const batches = collectBatches(records.current, seen.current, buckets.current);
          for (const batch of batches.slice(0, DEMO_LOT_LIMIT - tasks.current.length)) {
            tasks.current.push({ cqcId: `FE-DEMO-${session.current}-${tasks.current.length}`, batch, stage: 0, bidCount: 0 });
          }
        }
        for (const task of tasks.current.filter((item) => item.stage < 6)) {
          if (disposed) break;
          const message = await advanceTask(task, api, Date.now());
          if (!disposed && message) setEvents((previous) => [message, ...previous].slice(0, 6));
        }
        // 결제를 기다리는 첫 낙찰에만 결제 창을 띄운다. 창은 사용자가 결제를 마칠 때까지 남는다.
        for (const task of tasks.current) {
          if (disposed || task.stage !== 5 || !task.payment || task.paid) continue;
          if (!checkoutLot.current) { checkoutLot.current = task.payment.lotId; setPayment(task.payment); }
          else if (checkoutLot.current !== task.payment.lotId) {
            task.paid = true;
            setEvents((previous) => [`${task.payment!.lotId} 가상 결제 · 결제창 시연은 첫 낙찰 1건만`, ...previous].slice(0, 6));
          }
        }
        if (!disposed) {
          setCount(tasks.current.filter((task) => task.stage === 6).length);
          setBuffered([...buckets.current.values()].reduce((total, rows) => total + rows.length, 0));
          if (tasks.current.length === DEMO_LOT_LIMIT && tasks.current.every((task) => task.stage === 6)) setEnabled(false);
        }
      } catch (cause) {
        if (!disposed) { setError(cause instanceof Error ? cause.message : "자동 시연 실패"); setEnabled(false); }
      } finally { busy.current = false; }
    }
    const timer = setInterval(() => void tick(), DEMO_TICK_MS);
    return () => { disposed = true; controller.abort(); clearInterval(timer); };
  }, [enabled]);
  function markPaid(lotId: string, message: string) {
    const task = tasks.current.find((item) => item.lotId === lotId);
    if (task) task.paid = true;
    setEvents((previous) => [message, ...previous].slice(0, 6));
  }
  function closePayment() {
    // 결제를 마친 창만 닫힌다. 아직 결제 전이면 다음 진행 주기에 다시 뜬다.
    setPayment(null);
  }
  return <Context.Provider value={{ connection, enabled, count, buffered, events, error, payment, toggle, markPaid, closePayment }}>{children}</Context.Provider>;
}
export function AutoAuctionDemo() {
  const demo = useDemo();
  return <section className="auto-auction-demo" aria-label="자동 경매 시연">
    <div className="auto-demo-heading"><div><strong>검사부터 자동배차까지</strong><p>선별 라인 1 · 같은 선별함 {DEMO_LOT_SIZE}개 → 시연 1kg 출품 → {DEMO_AUCTION_MS / 1000}초 경매 → 낙찰자 결제(토스 테스트) → 배차</p></div>
      <button className="outline-button" onClick={demo.toggle} disabled={demo.count >= DEMO_LOT_LIMIT}>{demo.enabled ? "자동 시연 일시정지" : demo.error ? "자동 시연 재개" : demo.count >= DEMO_LOT_LIMIT ? "시연 완료" : "자동 시연 시작"}</button></div>
    <small>가상 구매자·물량·최저가 5,000원 · 토스페이먼츠 테스트 결제는 첫 낙찰 1건만(실제 출금 없음) · 최대 3건 · 새로고침은 새 시연 · 한 탭에서만 실행하세요.</small>
    <p role="status">{demo.enabled ? "자동 진행 중" : "자동 동작 정지"} · 분류별 대기 {demo.buffered}개 · 완료 {demo.count}/3건</p>
    {demo.error && <p role="alert" className="qc-warning">{demo.error} · 완료 단계는 유지됩니다. 연결·가용 차량 확인 후 재개하세요.</p>}
    {demo.events.length > 0 && <ol>{demo.events.map((message, index) => <li key={`${index}-${message}`}>{message}</li>)}</ol>}
    {demo.payment && <PaymentPopup key={demo.payment.lotId} payment={demo.payment} onPaid={demo.markPaid} onClose={demo.closePayment} />}
  </section>;
}
type Phase = { step: "ready" | "paying" | "done" | "failed"; message?: string; result?: Confirmed | null };
/** 낙찰자 입장의 결제 창. 토스페이먼츠 테스트 결제창으로 결제하고, 승인되어야 배차로 넘어간다. 저절로 닫히지 않는다. */
function PaymentPopup({ payment, onPaid, onClose }: { payment: DemoPayment; onPaid: (lotId: string, message: string) => void; onClose: () => void }) {
  const [config, setConfig] = useState<PaymentConfig | null>(null);
  const [phase, setPhase] = useState<Phase>({ step: "ready" });
  useEffect(() => { void fetchPaymentConfig().then(setConfig); }, []);
  // 자동 시연 구매자 ID는 "시연 마트-<시연 ID>" 형태라 앞의 이름만 보여 준다.
  const buyer = payment.buyerId.replace(/-FE-DEMO-.*$/, "");
  async function pay() {
    if (!config) return;
    setPhase({ step: "paying" });
    try {
      const result = await payWithToss(config, { orderId: paymentOrderId(payment.lotId), orderName: `CQC 사과 ${payment.lotId}`, amount: payment.priceWon, customerName: buyer });
      onPaid(payment.lotId, `${payment.lotId} 토스 테스트 결제 승인 · ${result.totalAmount.toLocaleString("ko-KR")}원`);
      setPhase({ step: "done", result });
    } catch (cause) {
      setPhase({ step: "failed", message: cause instanceof Error ? cause.message : "결제를 마치지 못했습니다" });
    }
  }
  function payVirtual() {
    onPaid(payment.lotId, `${payment.lotId} 가상 결제로 진행 · 실결제 없음`);
    setPhase({ step: "done", result: null });
  }
  const pgReady = config?.enabled === true;
  return <div className="payment-popup" role="dialog" aria-live="polite" aria-label="낙찰 결제">
    <div className="payment-card">
      <small>{buyer} 화면 · {pgReady ? "토스페이먼츠 테스트 결제" : "가상 결제"}</small>
      <strong>{phase.step === "done" ? "결제 완료" : "낙찰을 축하합니다"}</strong>
      <dl>
        <div><dt>출품</dt><dd>{payment.lotId}</dd></div>
        <div><dt>낙찰가</dt><dd>{payment.priceWon.toLocaleString("ko-KR")}원</dd></div>
        {phase.step === "done" && phase.result && <div><dt>결제 수단</dt><dd>{phase.result.method ?? "카드"} · 테스트</dd></div>}
        {phase.step === "done" && phase.result?.approvedAt && <div><dt>승인 시각</dt><dd>{new Date(phase.result.approvedAt).toLocaleTimeString("ko-KR")}</dd></div>}
      </dl>
      {phase.step === "ready" && <p>{config === null ? "결제 준비 중…" : pgReady ? "결제하기를 누르면 토스 테스트 결제창이 열립니다. 실제 돈은 나가지 않습니다." : `${config.reason} · 가상 결제로 진행할 수 있습니다.`}</p>}
      {phase.step === "paying" && <p>결제창에서 결제를 진행하세요…</p>}
      {phase.step === "failed" && <p className="failed">{phase.message}</p>}
      {phase.step === "done" && <p className="paid">{phase.result ? "결제가 승인되었습니다. 배차를 시작합니다." : "가상 결제로 처리했습니다. 배차를 시작합니다."}{phase.result?.receiptUrl && <> · <a href={phase.result.receiptUrl} target="_blank" rel="noopener noreferrer">영수증</a></>}</p>}
      <div className="payment-actions">
        {(phase.step === "ready" || phase.step === "failed") && pgReady && <button className="primary-button" onClick={() => void pay()}>{phase.step === "failed" ? "다시 결제" : "결제하기"}</button>}
        {(phase.step === "failed" || (phase.step === "ready" && config !== null && !pgReady)) && <button className="outline-button" onClick={payVirtual}>가상 결제로 진행</button>}
        {phase.step === "done" && <button className="primary-button" onClick={onClose}>확인</button>}
      </div>
    </div>
  </div>;
}
