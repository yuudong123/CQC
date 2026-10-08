import type { Result } from "./quality-runtime";

// 같은 선별함 2개를 한 출품으로 묶는다(4개는 2초 간격에서 첫 출품까지 1~2분 걸려 시연이 늘어졌다).
export const DEMO_LOT_SIZE = 2;
export const DEMO_LOT_LIMIT = 3;
/** 경매를 여는 시간과, 낙찰자 결제 팝업을 보여 주고 배차로 넘어가기까지의 시간. */
export const DEMO_AUCTION_MS = 6_000;
export const DEMO_PAYMENT_MS = 3_000;
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
type Order = { orderId: string; lotId: string; status: string; buyerId?: string; priceWon?: number };
export type DemoPayment = { lotId: string; buyerId: string; priceWon: number };
type Api = <T>(path: string, body?: unknown) => Promise<T>;
export type DemoTask = { cqcId: string; batch: DemoBatch; stage: number; bidCount: number; lotId?: string; orderId?: string; openedAt?: number; paid?: boolean; paidAt?: number; payment?: DemoPayment };

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
    return `검사 통과 ${DEMO_LOT_SIZE}개 묶음 등록 · 시연 환산 1kg`;
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
    if (lots.find((item) => item.lotId === task.lotId)?.auctionStatus !== "OPEN" || now - task.openedAt! >= DEMO_AUCTION_MS) {
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
    // 낙찰자 화면의 결제 팝업이 떠 있는 동안(DEMO_PAYMENT_MS)은 배차하지 않습니다.
    if (!task.paid) {
      task.paid = true; task.paidAt = now;
      if (order.buyerId && order.priceWon !== undefined) task.payment = { lotId: task.lotId!, buyerId: order.buyerId, priceWon: order.priceWon };
      return `${task.lotId} 결제 완료(가상) · 실결제 없음`;
    }
    if (task.paidAt !== undefined && now - task.paidAt < DEMO_PAYMENT_MS) return "";
    if (order.status === "MATCHED" || order.status === "DISPATCHING") await api(`/orders/${task.orderId}/dispatch`, {});
    task.stage++;
    return `${task.lotId} 자동 배차 완료 · 관제에서 확인`;
  }
  return "";
}
