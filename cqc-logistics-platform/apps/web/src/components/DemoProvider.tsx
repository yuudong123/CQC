"use client";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { useQualityConnection } from "./useQualityConnection";
import { advanceTask, collectBatches, DEMO_AUCTION_MS, DEMO_LOT_LIMIT, DEMO_LOT_SIZE, DEMO_PAYMENT_MS, type DemoPayment, type DemoTask } from "@/lib/auction-demo";
import type { Result } from "@/lib/quality-runtime";
import { logisticsFetch } from "@/lib/logistics-client";
type Demo = { connection: ReturnType<typeof useQualityConnection>; enabled: boolean; count: number; buffered: number; events: string[]; error: string; payment: DemoPayment | null; toggle: () => void };
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
  const shownPayments = useRef(new Set<string>());
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
          if (!disposed && task.payment && !shownPayments.current.has(task.payment.lotId)) {
            const shown = task.payment;
            shownPayments.current.add(shown.lotId);
            setPayment(shown);
            // 다른 페이지에 갔다 와도 지난 결제 창이 다시 뜨지 않게 표시 시간이 지나면 지운다.
            setTimeout(() => setPayment((current) => (current?.lotId === shown.lotId ? null : current)), DEMO_PAYMENT_MS);
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
  return <Context.Provider value={{ connection, enabled, count, buffered, events, error, payment, toggle }}>{children}</Context.Provider>;
}
export function AutoAuctionDemo() {
  const demo = useDemo();
  return <section className="auto-auction-demo" aria-label="자동 경매 시연">
    <div className="auto-demo-heading"><div><strong>검사부터 자동배차까지</strong><p>선별 라인 1 · 같은 선별함 {DEMO_LOT_SIZE}개 → 시연 1kg 출품 → {DEMO_AUCTION_MS / 1000}초 경매 → 낙찰자 결제(가상) → 배차</p></div>
      <button className="outline-button" onClick={demo.toggle} disabled={demo.count >= DEMO_LOT_LIMIT}>{demo.enabled ? "자동 시연 일시정지" : demo.error ? "자동 시연 재개" : demo.count >= DEMO_LOT_LIMIT ? "시연 완료" : "자동 시연 시작"}</button></div>
    <small>가상 구매자·물량·최저가 5,000원 · 실결제 없음 · 최대 3건 · 새로고침은 새 시연 · 한 탭에서만 실행하세요.</small>
    <p role="status">{demo.enabled ? "자동 진행 중" : "자동 동작 정지"} · 분류별 대기 {demo.buffered}개 · 완료 {demo.count}/3건</p>
    {demo.error && <p role="alert" className="qc-warning">{demo.error} · 완료 단계는 유지됩니다. 연결·가용 차량 확인 후 재개하세요.</p>}
    {demo.events.length > 0 && <ol>{demo.events.map((message, index) => <li key={`${index}-${message}`}>{message}</li>)}</ol>}
    {demo.payment && <PaymentPopup key={demo.payment.lotId} payment={demo.payment} />}
  </section>;
}
/** 낙찰자 입장에서 보는 가상 결제 창. 잠깐 "결제 중"을 보여 준 뒤 완료로 바뀌고 저절로 닫힌다. */
function PaymentPopup({ payment }: { payment: DemoPayment }) {
  const [phase, setPhase] = useState<"paying" | "done" | "closed">("paying");
  useEffect(() => {
    const done = setTimeout(() => setPhase("done"), DEMO_PAYMENT_MS * 0.4);
    const close = setTimeout(() => setPhase("closed"), DEMO_PAYMENT_MS);
    return () => { clearTimeout(done); clearTimeout(close); };
  }, []);
  if (phase === "closed") return null;
  // 자동 시연 구매자 ID는 "시연 마트-<시연 ID>" 형태라 앞의 이름만 보여 준다.
  const buyer = payment.buyerId.replace(/-FE-DEMO-.*$/, "");
  return <div className="payment-popup" role="dialog" aria-live="polite" aria-label="낙찰 결제">
    <div className="payment-card">
      <small>{buyer} 화면 · 가상 결제</small>
      <strong>{phase === "paying" ? "낙찰을 축하합니다" : "결제 완료"}</strong>
      <dl>
        <div><dt>출품</dt><dd>{payment.lotId}</dd></div>
        <div><dt>낙찰가</dt><dd>{payment.priceWon.toLocaleString("ko-KR")}원</dd></div>
        <div><dt>결제 수단</dt><dd>시연 카드 · 실결제 없음</dd></div>
      </dl>
      <p className={phase === "done" ? "paid" : ""}>{phase === "paying" ? "결제 진행 중…" : "결제가 완료되었습니다. 곧 배차를 시작합니다."}</p>
    </div>
  </div>;
}
