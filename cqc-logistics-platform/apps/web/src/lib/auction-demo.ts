import type { Result } from "./quality-runtime";

export const DEMO_LOT_SIZE = 4;
export const DEMO_LOT_LIMIT = 3;
export type DemoBatch = { key: string; rows: Result[] };

/** 통과·저장·선별 성공 건만 묶습니다. 당도 경계는 검사 결과의 선별 목적지를 따릅니다. */
export function collectBatches(records: Result[], seen: Set<string>, buckets: Map<string, Result[]>): DemoBatch[] {
  const batches: DemoBatch[] = [];
  for (const row of [...records].reverse()) {
    if (seen.has(row.id)) continue;
    seen.add(row.id);
    if (row.status !== "PASS" || !row.variety || !row.grade || row.confidence === null || row.excluded || row.reviewRequired || row.persistence !== "SAVED" || row.control !== "SUCCEEDED" || row.errorCode !== "NONE" || row.misclassification !== "NONE" || row.virtualBrix === null || !/^DEMO_BIN_\d{2}$/.test(row.bin)) continue;
    const key = `${row.variety}/${row.grade}/${row.bin}`;
    const rows = [...(buckets.get(key) ?? []), row];
    if (rows.length === DEMO_LOT_SIZE) { batches.push({ key, rows }); buckets.delete(key); }
    else buckets.set(key, rows);
  }
  return batches;
}
type Lot = { lotId: string; cqcId: string; auctionStatus: string };
type Order = { orderId: string; lotId: string; status: string };
type Api = <T>(path: string, body?: unknown) => Promise<T>;
export type DemoTask = { cqcId: string; batch: DemoBatch; stage: number; bidCount: number; lotId?: string; orderId?: string; openedAt?: number; paid?: boolean };

/** 서버 조회로 진행 단계를 복구하여 응답 유실 후에도 출품·낙찰·배차를 중복 생성하지 않습니다. */
export async function advanceTask(task: DemoTask, api: Api, now: number): Promise<string> {
  const row = task.batch.rows[0];
  if (task.stage === 0) {
    await api("/cqc-results", {
      cqcId: task.cqcId, farmId: "farm-demo-line-1", crop: "apple",
      variety: row.variety === "부사" ? "fuji" : "yanggwang",
      qualityGrade: ({ 특: "SPECIAL", 상: "PREMIUM", 보통: "STANDARD" })[row.grade!],
      confidence: Math.min(...task.batch.rows.map((item) => item.confidence ?? 0)) / 100,
      quantityKg: 1, origin: { type: "Point", coordinates: [127.004, 36.789] },
      rawPayload: { source: "frontend-auto-demo", model_version: row.modelVersion, line_id: "line-1", inspection_ids: task.batch.rows.map((item) => item.id), virtual_brix: task.batch.rows.map((item) => item.virtualBrix), brix_is_measured: false, quantity_is_simulated: true },
    });
    task.stage++;
    return "검사 통과 4개 묶음 등록 · 시연 환산 1kg";
  }
  if (task.stage === 1) {
    const lots = await api<Lot[]>("/lots");
    const lot = lots.find((item) => item.cqcId === task.cqcId) ?? await api<Lot>("/lots", { cqcId: task.cqcId, reservePriceWon: 5000, closesAt: new Date(now + 60_000).toISOString() });
    task.lotId = lot.lotId; task.stage++;
    return `${lot.lotId} 자동 출품`;
  }
  if (task.stage === 2) {
    const lot = (await api<Lot[]>("/lots")).find((item) => item.lotId === task.lotId);
    if (!lot) throw new Error("시연 출품이 없어졌습니다. 서버 초기화 여부를 확인하세요.");
    if (lot?.auctionStatus === "DRAFT") await api(`/lots/${task.lotId}/open`, {});
    task.openedAt = now; task.stage++;
    return `${task.lotId} 경매 시작`;
  }
  if (task.stage === 3) {
    const lots = await api<Lot[]>("/lots");
    if (lots.find((item) => item.lotId === task.lotId)?.auctionStatus !== "OPEN" || now - task.openedAt! >= 12_000) {
      task.stage++; return "자동 경매 마감 대기";
    }
    const bids = await api<{ buyerId: string; priceWon: number }[]>(`/lots/${task.lotId}/bids`);
    const names = ["시연 마트", "시연 식당", "시연 유통사"];
    if (task.bidCount < names.length) {
      const buyerId = `${names[task.bidCount]}-${task.cqcId}`;
      if (!bids.some((bid) => bid.buyerId === buyerId)) await api(`/lots/${task.lotId}/bids`, {
        buyerId, priceWon: Math.max(5000, ...bids.map((bid) => bid.priceWon)) + 500,
        destination: { type: "Point", coordinates: [127.028 + task.bidCount * 0.01, 37.498] },
      });
      task.bidCount++;
      return `${task.lotId} · ${names[task.bidCount - 1]} 자동 입찰`;
    }
    return "";
  }
  if (task.stage === 4) {
    const overview = await api<{ orders: Order[] }>("/control/overview");
    let order = overview.orders.find((item) => item.lotId === task.lotId);
    if (!order) {
      const lot = (await api<Lot[]>("/lots")).find((item) => item.lotId === task.lotId);
      if (lot?.auctionStatus === "CLOSED_UNSOLD") { task.stage = 6; return "입찰 없이 마감 · 배차 없음"; }
      const result = await api<{ order: Order | null }>(`/lots/${task.lotId}/close`, {});
      order = result.order ?? undefined;
    }
    task.orderId = order?.orderId; task.stage = order ? 5 : 6;
    return order ? `${task.lotId} 낙찰 · 주문 생성` : "입찰 없이 마감 · 배차 없음";
  }
  if (task.stage === 5) {
    const order = await api<Order>(`/orders/${task.orderId}`);
    if (order.status === "CANCELLED") { task.stage = 6; return `${task.lotId} 주문 취소 · 배차하지 않음`; }
    // 결제 API는 없으므로 낙찰과 배차 사이에 가상 결제 단계만 한 번 보여줍니다.
    if (!task.paid) { task.paid = true; return `${task.lotId} 결제 완료(가상) · 실결제 없음`; }
    if (order.status === "MATCHED" || order.status === "DISPATCHING") await api(`/orders/${task.orderId}/dispatch`, {});
    task.stage++;
    return `${task.lotId} 자동 배차 완료 · 관제에서 확인`;
  }
  return "";
}
