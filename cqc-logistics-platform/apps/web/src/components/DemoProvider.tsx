"use client";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { useQualityConnection } from "./useQualityConnection";
import { advanceTask, collectBatches, DEMO_LOT_LIMIT, type DemoTask } from "@/lib/auction-demo";
import type { Result } from "@/lib/quality-runtime";
import { logisticsFetch } from "@/lib/logistics-client";
type Demo = { connection: ReturnType<typeof useQualityConnection>; enabled: boolean; count: number; buffered: number; events: string[]; error: string; toggle: () => void };
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
        if (!disposed) {
          setCount(tasks.current.filter((task) => task.stage === 6).length);
          setBuffered([...buckets.current.values()].reduce((total, rows) => total + rows.length, 0));
          if (tasks.current.length === DEMO_LOT_LIMIT && tasks.current.every((task) => task.stage === 6)) setEnabled(false);
        }
      } catch (cause) {
        if (!disposed) { setError(cause instanceof Error ? cause.message : "자동 시연 실패"); setEnabled(false); }
      } finally { busy.current = false; }
    }
    const timer = setInterval(() => void tick(), 1500);
    return () => { disposed = true; controller.abort(); clearInterval(timer); };
  }, [enabled]);
  return <Context.Provider value={{ connection, enabled, count, buffered, events, error, toggle }}>{children}</Context.Provider>;
}
export function AutoAuctionDemo() {
  const demo = useDemo();
  return <section className="auto-auction-demo" aria-label="자동 경매 시연">
    <div className="auto-demo-heading"><div><strong>검사부터 자동배차까지</strong><p>선별 라인 1 · 같은 분류 4개 → 시연 1kg 출품 → 12초 경매 → 결제(가상) → 배차</p></div>
      <button className="outline-button" onClick={demo.toggle} disabled={demo.count >= DEMO_LOT_LIMIT}>{demo.enabled ? "자동 시연 일시정지" : demo.error ? "자동 시연 재개" : demo.count >= DEMO_LOT_LIMIT ? "시연 완료" : "자동 시연 시작"}</button></div>
    <small>가상 구매자·물량·최저가 5,000원 · 실결제 없음 · 최대 3건 · 새로고침은 새 시연 · 한 탭에서만 실행하세요.</small>
    <p role="status">{demo.enabled ? "자동 진행 중" : "자동 동작 정지"} · 분류별 대기 {demo.buffered}개 · 완료 {demo.count}/3건</p>
    {demo.error && <p role="alert" className="qc-warning">{demo.error} · 완료 단계는 유지됩니다. 연결·가용 차량 확인 후 재개하세요.</p>}
    {demo.events.length > 0 && <ol>{demo.events.map((message, index) => <li key={`${index}-${message}`}>{message}</li>)}</ol>}
  </section>;
}
