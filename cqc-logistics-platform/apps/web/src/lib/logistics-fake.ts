/**
 * 시연용 가상 물류 서버. apps/api의 MemoryStore와 라우트 응답을 브라우저 안에서 흉내 낸다.
 * 물류 API·MongoDB 없이 출품·입찰·낙찰·배차·배송 관제 화면이 동작하며, 상태는 같은 브라우저의 탭끼리 localStorage로 공유한다.
 */
type Point = { type: "Point"; coordinates: [number, number] };
type Doc = Record<string, unknown>;
type Cqc = Doc & { cqcId: string; farmId: string; crop: string; variety: string; qualityGrade: string; quantityKg: number; origin: Point; createdAt: string };
type Lot = Doc & { lotId: string; cqcId: string; sellerId: string; variety: string; qualityGrade: string; quantityKg: number; origin: Point; reservePriceWon: number; auctionStatus: string; closesAt: string; createdAt: string; updatedAt: string };
type Bid = { bidId: string; lotId: string; buyerId: string; priceWon: number; destination: Point; accepted: boolean; placedAt: string };
type Order = { orderId: string; lotId: string; sellerId: string; buyerId: string; quantityKg: number; priceWon: number; origin: Point; destination: Point; status: string; fleetId: string | null; routeId: string | null; createdAt: string; updatedAt: string };
type Fleet = { fleetId: string; name: string; capacityKg: number; location: Point; currentLoadKg: number; status: string; lastPositionAt: string };
type Stop = { sequence: number; type: "PICKUP" | "DROPOFF"; orderId: string; location: Point; status: string; arrivedAt?: string };
type Route = { routeId: string; fleetId: string; version: number; status: string; stops: Stop[]; distanceKm: number; estimatedMinutes: number; createdAt: string; updatedAt: string };
type State = { version: 1; cqc: Record<string, Cqc>; lots: Record<string, Lot>; bids: Record<string, Bid[]>; orders: Record<string, Order>; fleets: Record<string, Fleet>; routes: Record<string, Route> };

const STORAGE_KEY = "cqc-logistics-fake-v1";
/** 상차·하차 확인 화면이 없으므로 도착 후 이 시간이 지나면 작업자가 확인한 것으로 처리한다. */
export const GATE_AUTO_COMPLETE_MS = 3000;
const ORIGIN: Point = { type: "Point", coordinates: [127.017, 36.806] };
const SEOUL: Point = { type: "Point", coordinates: [127.028, 37.498] };

class FakeError extends Error {
  constructor(readonly status: number, message: string) { super(message); }
}
const iso = (ms: number) => new Date(ms).toISOString();
const hex = () => Array.from(crypto.getRandomValues(new Uint8Array(5)), (value) => value.toString(16).padStart(2, "0")).join("");
const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value));

function distanceKm(first: Point, second: Point) {
  const [lon1, lat1d] = first.coordinates; const [lon2, lat2d] = second.coordinates;
  const rad = Math.PI / 180, lat1 = lat1d * rad, lat2 = lat2d * rad;
  const a = Math.sin((lat2 - lat1) / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(((lon2 - lon1) * rad) / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(a));
}
function moveTowards(current: Point, target: Point, maxKm = 20): [Point, boolean] {
  const distance = distanceKm(current, target);
  if (distance <= maxKm || distance === 0) return [clone(target), true];
  const ratio = maxKm / distance;
  const [lon, lat] = current.coordinates; const [tLon, tLat] = target.coordinates;
  return [{ type: "Point", coordinates: [lon + (tLon - lon) * ratio, lat + (tLat - lat) * ratio] }, false];
}
function recalculate(route: Route, current: Point) {
  const points = [current, ...route.stops.filter((stop) => stop.status !== "COMPLETED").map((stop) => stop.location)];
  let total = 0;
  for (let i = 1; i < points.length; i++) total += distanceKm(points[i - 1], points[i]);
  route.distanceKm = Math.round(total * 10) / 10;
  route.estimatedMinutes = Math.max(1, Math.round(route.distanceKm * 2));
}
const byDesc = <T,>(key: (item: T) => string) => (a: T, b: T) => key(b).localeCompare(key(a));

export class FakeLogisticsStore {
  state: State;
  constructor(state?: State, private readonly now: () => number = Date.now) {
    this.state = state ?? FakeLogisticsStore.empty();
    if (!state) this.seed();
  }
  static empty(): State { return { version: 1, cqc: {}, lots: {}, bids: {}, orders: {}, fleets: {}, routes: {} }; }

  saveCqc(payload: Doc) {
    const cqcId = String(payload.cqcId ?? "");
    if (!cqcId || !payload.farmId || !payload.variety || !payload.qualityGrade || !(Number(payload.quantityKg) > 0)) throw new FakeError(422, "CQC 결과 형식이 올바르지 않습니다.");
    const document = { crop: "apple", rawPayload: {}, ...clone(payload), createdAt: this.state.cqc[cqcId]?.createdAt ?? iso(this.now()) } as unknown as Cqc;
    this.state.cqc[cqcId] = document;
    return document;
  }
  createLot(payload: { cqcId: string; reservePriceWon: number; suggestedPriceWon?: number | null; closesAt?: string | null }) {
    const cqc = this.state.cqc[payload.cqcId];
    if (!cqc) throw new FakeError(404, "CQC 결과를 찾을 수 없습니다.");
    if (!(payload.reservePriceWon > 0)) throw new FakeError(422, "최저 낙찰가는 0보다 커야 합니다.");
    const now = this.now();
    const lot: Lot = {
      lotId: `lot-${hex()}`, cqcId: cqc.cqcId, sellerId: cqc.farmId, crop: cqc.crop, variety: cqc.variety,
      qualityGrade: cqc.qualityGrade, quantityKg: cqc.quantityKg, origin: clone(cqc.origin),
      reservePriceWon: payload.reservePriceWon, suggestedPriceWon: payload.suggestedPriceWon ?? null, auctionStatus: "DRAFT",
      closesAt: payload.closesAt ? iso(Date.parse(payload.closesAt)) : iso(now + 10 * 60_000), createdAt: iso(now), updatedAt: iso(now),
    };
    this.state.lots[lot.lotId] = lot;
    return lot;
  }
  listLots(status?: string | null) {
    return Object.values(this.state.lots).filter((lot) => !status || lot.auctionStatus === status).sort(byDesc((lot) => lot.createdAt));
  }
  openLot(lotId: string) {
    const lot = this.state.lots[lotId];
    if (!lot || lot.auctionStatus !== "DRAFT") throw new FakeError(409, "출품이 없거나 이미 시작된 경매입니다.");
    lot.auctionStatus = "OPEN"; lot.updatedAt = iso(this.now());
    return lot;
  }
  placeBid(lotId: string, payload: { buyerId: string; priceWon: number; destination: Point }) {
    const lot = this.state.lots[lotId];
    if (!lot || lot.auctionStatus !== "OPEN") throw new FakeError(409, "진행 중인 경매가 아닙니다.");
    if (!payload.buyerId?.trim() || !(payload.priceWon > 0)) throw new FakeError(422, "입찰 형식이 올바르지 않습니다.");
    const bids = (this.state.bids[lotId] ??= []);
    const highest = Math.max(0, ...bids.map((bid) => bid.priceWon));
    if (payload.priceWon < lot.reservePriceWon) throw new FakeError(409, "최저 낙찰가보다 낮은 입찰입니다.");
    if (payload.priceWon <= highest) throw new FakeError(409, "현재 최고 입찰가보다 높아야 합니다.");
    const bid: Bid = { bidId: `bid-${hex()}`, lotId, buyerId: payload.buyerId, priceWon: payload.priceWon, destination: clone(payload.destination ?? SEOUL), accepted: true, placedAt: iso(this.now()) };
    bids.push(bid);
    return bid;
  }
  listBids(lotId: string) {
    if (!this.state.lots[lotId]) throw new FakeError(404, "출품을 찾을 수 없습니다.");
    return [...(this.state.bids[lotId] ?? [])].sort((a, b) => b.priceWon - a.priceWon || b.placedAt.localeCompare(a.placedAt));
  }
  closeLot(lotId: string) {
    const lot = this.state.lots[lotId];
    if (!lot || lot.auctionStatus !== "OPEN") throw new FakeError(409, "경매가 없거나 이미 종료되었습니다.");
    const bids = this.listBids(lotId);
    lot.auctionStatus = bids.length ? "AWARDED" : "CLOSED_UNSOLD"; lot.updatedAt = iso(this.now());
    const order = bids.length ? this.createOrder(lot, bids[0]) : null;
    return { lot, winningBid: bids[0] ?? null, order };
  }
  createOrder(lot: Lot, bid: Bid) {
    const existing = Object.values(this.state.orders).find((order) => order.lotId === lot.lotId);
    if (existing) return existing;
    const now = iso(this.now());
    const order: Order = { orderId: `order-${hex()}`, lotId: lot.lotId, sellerId: lot.sellerId, buyerId: bid.buyerId, quantityKg: lot.quantityKg, priceWon: bid.priceWon, origin: clone(lot.origin), destination: clone(bid.destination), status: "MATCHED", fleetId: null, routeId: null, createdAt: now, updatedAt: now };
    this.state.orders[order.orderId] = order;
    return order;
  }
  getOrder(orderId: string) {
    const order = this.state.orders[orderId];
    if (!order) throw new FakeError(404, "주문을 찾을 수 없습니다.");
    return order;
  }
  createFleet(name: string, capacityKg: number, location: Point) {
    const fleet: Fleet = { fleetId: `fleet-${hex()}`, name, capacityKg, location: clone(location), currentLoadKg: 0, status: "IDLE", lastPositionAt: iso(this.now()) };
    this.state.fleets[fleet.fleetId] = fleet;
    return fleet;
  }
  private activeRoute(fleetId: string) {
    return Object.values(this.state.routes).find((route) => route.fleetId === fleetId && route.status === "ACTIVE");
  }
  dispatch(orderId: string) {
    const order = this.getOrder(orderId);
    if (order.status !== "MATCHED") throw new FakeError(409, "이미 배차된 주문입니다.");
    const fleets = Object.values(this.state.fleets);
    const free = (fleet: Fleet) => fleet.capacityKg - fleet.currentLoadKg >= order.quantityKg;
    const idle = fleets.filter((fleet) => fleet.status === "IDLE" && free(fleet));
    const now = iso(this.now());
    if (!idle.length) {
      const active = fleets.flatMap((fleet) => {
        const route = this.activeRoute(fleet.fleetId);
        return route && ["TO_PICKUP", "WAITING_LOAD", "IN_TRANSIT", "WAITING_UNLOAD"].includes(fleet.status) && free(fleet) ? [[fleet, route] as const] : [];
      });
      if (!active.length) throw new FakeError(409, "조건에 맞는 가용 차량이 없습니다.");
      const cost = ([fleet]: readonly [Fleet, Route]) => distanceKm(fleet.location, order.origin) + distanceKm(order.origin, order.destination);
      const [fleet, route] = active.reduce((best, item) => (cost(item) < cost(best) ? item : best));
      const insertAt = route.stops.findIndex((stop) => stop.status !== "COMPLETED" && stop.type === "DROPOFF");
      route.stops.splice(insertAt < 0 ? route.stops.length : insertAt, 0,
        { sequence: 0, type: "PICKUP", orderId, location: clone(order.origin), status: "PENDING" },
        { sequence: 0, type: "DROPOFF", orderId, location: clone(order.destination), status: "PENDING" });
      route.stops.forEach((stop, index) => { stop.sequence = index + 1; });
      route.version += 1; recalculate(route, fleet.location); route.updatedAt = now;
      fleet.currentLoadKg += order.quantityKg; fleet.lastPositionAt = now;
      Object.assign(order, { status: "ASSIGNED", fleetId: fleet.fleetId, routeId: route.routeId, updatedAt: now });
      return { order, fleet, route };
    }
    const fleet = idle.reduce((best, item) => (distanceKm(item.location, order.origin) < distanceKm(best.location, order.origin) ? item : best));
    const distance = distanceKm(order.origin, order.destination);
    const route: Route = {
      routeId: `route-${hex()}`, fleetId: fleet.fleetId, version: 1, status: "ACTIVE",
      stops: [
        { sequence: 1, type: "PICKUP", orderId, location: clone(order.origin), status: "PENDING" },
        { sequence: 2, type: "DROPOFF", orderId, location: clone(order.destination), status: "PENDING" },
      ],
      distanceKm: Math.round(distance * 10) / 10, estimatedMinutes: Math.max(1, Math.round(distance * 2)), createdAt: now, updatedAt: now,
    };
    fleet.currentLoadKg += order.quantityKg; fleet.status = "TO_PICKUP"; fleet.lastPositionAt = now;
    Object.assign(order, { status: "ASSIGNED", fleetId: fleet.fleetId, routeId: route.routeId, updatedAt: now });
    this.state.routes[route.routeId] = route;
    return { order, fleet, route };
  }
  simulateStep(fleetId: string) {
    const fleet = this.state.fleets[fleetId];
    if (!fleet) throw new FakeError(404, "차량을 찾을 수 없습니다.");
    const route = this.activeRoute(fleetId);
    const stop = route?.stops.find((item) => item.status !== "COMPLETED");
    if (!route || !stop) throw new FakeError(409, "진행 중인 노선이 없습니다.");
    const [position, arrived] = moveTowards(fleet.location, stop.location);
    const now = iso(this.now());
    fleet.location = position; fleet.lastPositionAt = now;
    const order = this.state.orders[stop.orderId];
    if (arrived) {
      stop.status = "ARRIVED"; stop.arrivedAt = now;
      fleet.status = stop.type === "PICKUP" ? "WAITING_LOAD" : "WAITING_UNLOAD";
      if (order) { order.status = stop.type === "PICKUP" ? "PICKUP_ARRIVED" : "DELIVERY_ARRIVED"; order.updatedAt = now; }
    } else fleet.status = stop.type === "PICKUP" ? "TO_PICKUP" : "IN_TRANSIT";
    route.updatedAt = now;
    return { fleet, route, arrived };
  }
  /** 도착 후 GATE_AUTO_COMPLETE_MS가 지난 상차·하차를 완료 처리한다. 실제 API의 load-complete·unload-complete와 같은 전이다. */
  completeGates() {
    const now = this.now();
    for (const route of Object.values(this.state.routes).filter((item) => item.status === "ACTIVE")) {
      const stop = route.stops.find((item) => item.status !== "COMPLETED");
      if (!stop || stop.status !== "ARRIVED" || now - Date.parse(stop.arrivedAt ?? iso(now)) < GATE_AUTO_COMPLETE_MS) continue;
      const fleet = this.state.fleets[route.fleetId], order = this.state.orders[stop.orderId];
      if (!fleet || !order || fleet.status === "OUT_OF_SERVICE") continue;
      const stamp = iso(now);
      stop.status = "COMPLETED"; route.updatedAt = stamp; order.updatedAt = stamp; fleet.lastPositionAt = stamp;
      if (stop.type === "PICKUP") { order.status = "LOADED"; fleet.status = "IN_TRANSIT"; continue; }
      order.status = "DELIVERED";
      fleet.currentLoadKg = Math.max(0, fleet.currentLoadKg - order.quantityKg);
      const remaining = route.stops.find((item) => item.status !== "COMPLETED");
      route.status = remaining ? "ACTIVE" : "COMPLETED";
      fleet.status = remaining ? (remaining.type === "PICKUP" ? "TO_PICKUP" : "IN_TRANSIT") : "IDLE";
    }
  }
  breakdown(fleetId: string) {
    const fleet = this.state.fleets[fleetId];
    if (!fleet) throw new FakeError(404, "차량을 찾을 수 없습니다.");
    if (fleet.status === "OUT_OF_SERVICE") throw new FakeError(409, "이미 고장 처리된 차량입니다.");
    const now = iso(this.now());
    Object.assign(fleet, { status: "OUT_OF_SERVICE", currentLoadKg: 0, lastPositionAt: now });
    const route = this.activeRoute(fleetId);
    if (!route) return { brokenFleet: fleet, previousRoute: null, replacementFleet: null, replacementRoute: null, orders: [] };
    route.status = "CANCELLED"; route.updatedAt = now;
    const remaining = route.stops.filter((stop) => stop.status !== "COMPLETED");
    const orders = [...new Set(remaining.map((stop) => stop.orderId))].map((id) => this.state.orders[id]).filter(Boolean);
    const required = orders.reduce((total, order) => total + order.quantityKg, 0);
    const candidates = Object.values(this.state.fleets).filter((item) => item.status === "IDLE" && item.capacityKg - item.currentLoadKg >= required);
    if (!candidates.length || !remaining.length) return { brokenFleet: fleet, previousRoute: route, replacementFleet: null, replacementRoute: null, orders };
    const replacement = candidates.reduce((best, item) => (distanceKm(item.location, remaining[0].location) < distanceKm(best.location, remaining[0].location) ? item : best));
    const replacementRoute: Route = { routeId: `route-${hex()}`, fleetId: replacement.fleetId, version: 1, status: "ACTIVE", stops: clone(remaining), distanceKm: 0, estimatedMinutes: 1, createdAt: now, updatedAt: now };
    replacementRoute.stops.forEach((stop, index) => { stop.sequence = index + 1; });
    recalculate(replacementRoute, replacement.location);
    replacement.currentLoadKg += required;
    const first = replacementRoute.stops[0];
    replacement.status = first.status === "ARRIVED" ? (first.type === "PICKUP" ? "WAITING_LOAD" : "WAITING_UNLOAD") : first.type === "PICKUP" ? "TO_PICKUP" : "IN_TRANSIT";
    replacement.lastPositionAt = now;
    this.state.routes[replacementRoute.routeId] = replacementRoute;
    for (const order of orders) {
      Object.assign(order, { fleetId: replacement.fleetId, routeId: replacementRoute.routeId, updatedAt: now });
      if (!["LOADED", "DELIVERY_ARRIVED"].includes(order.status)) order.status = "ASSIGNED";
    }
    return { brokenFleet: fleet, previousRoute: route, replacementFleet: replacement, replacementRoute, orders };
  }
  overview() {
    this.completeGates();
    const fleets = Object.values(this.state.fleets);
    const orders = Object.values(this.state.orders).sort(byDesc((order) => order.updatedAt));
    const routes = Object.values(this.state.routes).sort(byDesc((route) => route.updatedAt));
    const alerts: Doc[] = [];
    for (const fleet of fleets) {
      if (fleet.status === "OUT_OF_SERVICE") alerts.push({ alertId: `fleet-breakdown-${fleet.fleetId}`, severity: "CRITICAL", title: "차량 고장 격리", message: `${fleet.name} 차량이 운행에서 제외됐습니다.`, createdAt: fleet.lastPositionAt });
      else if (fleet.status === "WAITING_LOAD" || fleet.status === "WAITING_UNLOAD") {
        const action = fleet.status === "WAITING_LOAD" ? "상차" : "하차";
        alerts.push({ alertId: `fleet-gate-${fleet.fleetId}`, severity: "WARNING", title: `${action} 확인 필요`, message: `${fleet.name} 차량이 ${action} 완료를 기다립니다.`, createdAt: fleet.lastPositionAt });
      }
    }
    for (const order of orders) if (order.status === "MATCHED") alerts.push({ alertId: `order-dispatch-${order.orderId}`, severity: "INFO", title: "배차 필요", message: `주문 ${order.orderId}이 배차를 기다립니다.`, createdAt: order.updatedAt });
    return {
      storage: "browser-demo", generatedAt: iso(this.now()), fleets, orders, routes, alerts,
      stats: {
        openAuctions: this.listLots("OPEN").length,
        activeFleets: fleets.filter((fleet) => !["IDLE", "OUT_OF_SERVICE"].includes(fleet.status)).length,
        inTransitOrders: orders.filter((order) => !["MATCHED", "DELIVERED", "CANCELLED"].includes(order.status)).length,
        attentionRequired: alerts.filter((alert) => alert.severity !== "INFO").length,
      },
    };
  }
  /** apps/api seed_demo_data와 같은 발표용 초기 상태. */
  seed() {
    this.state = FakeLogisticsStore.empty();
    const first = this.saveCqc({ cqcId: "CQC-demo-market-001", farmId: "farm-asan", variety: "fuji", qualityGrade: "SPECIAL", confidence: 0.96, quantityKg: 500, origin: ORIGIN });
    this.openLot(this.createLot({ cqcId: first.cqcId, reservePriceWon: 1_200_000 }).lotId);
    const second = this.saveCqc({ cqcId: "CQC-demo-route-001", farmId: "farm-chungju", variety: "hongro", qualityGrade: "PREMIUM", confidence: 0.93, quantityKg: 500, origin: ORIGIN });
    const lot = this.createLot({ cqcId: second.cqcId, reservePriceWon: 900_000 });
    this.openLot(lot.lotId);
    this.placeBid(lot.lotId, { buyerId: "buyer-seoul-mart", priceWon: 980_000, destination: SEOUL });
    const { order } = this.closeLot(lot.lotId);
    this.createFleet("CQC-01", 2_000, ORIGIN);
    this.createFleet("CQC-02", 4_000, { type: "Point", coordinates: [129.0756, 35.1796] });
    this.createFleet("CQC-03", 2_000, { type: "Point", coordinates: [127.3845, 36.3504] });
    this.dispatch(order!.orderId);
  }

  /** 실제 물류 API 경로와 같은 요청을 처리해 fetch와 같은 Response를 돌려준다. */
  handle(method: string, rawPath: string, body?: unknown): Response {
    const url = new URL(rawPath, "http://fake.local");
    const parts = url.pathname.split("/").filter(Boolean);
    const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
    const payload = (body ?? {}) as Doc & { cqcId: string; reservePriceWon: number; buyerId: string; priceWon: number; destination: Point };
    try {
      const [a, id, action] = parts;
      if (method === "POST" && a === "cqc-results" && !id) return json(this.saveCqc(payload), 201);
      if (a === "lots" && !id) return method === "POST" ? json(this.createLot(payload), 201) : json(this.listLots(url.searchParams.get("auction_status")));
      if (a === "lots" && method === "POST" && action === "open") return json(this.openLot(id));
      if (a === "lots" && action === "bids") return method === "POST" ? json(this.placeBid(id, payload), 201) : json(this.listBids(id));
      if (a === "lots" && method === "POST" && action === "close") return json(this.closeLot(id));
      if (a === "orders" && method === "GET" && id && !action) return json(this.getOrder(id));
      if (a === "orders" && method === "POST" && action === "dispatch") return json(this.dispatch(id));
      if (a === "fleets" && method === "GET" && !id) return json(Object.values(this.state.fleets));
      if (a === "fleets" && method === "POST" && action === "simulate-step") return json(this.simulateStep(id));
      if (a === "fleets" && method === "POST" && action === "breakdown") return json(this.breakdown(id));
      if (a === "control" && id === "overview" && method === "GET") return json(this.overview());
      if (a === "control" && id === "seed-reset" && method === "POST") { this.seed(); return json(this.overview()); }
      return json({ detail: "지원하지 않는 시연 경로입니다." }, 404);
    } catch (error) {
      if (error instanceof FakeError) return json({ detail: error.message }, error.status);
      throw error;
    }
  }
}

function load(): State | undefined {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const state = raw ? (JSON.parse(raw) as State) : undefined;
    return state?.version === 1 ? state : undefined;
  } catch { return undefined; }
}
let memory: State | undefined;
/** 요청마다 저장된 상태를 읽고 쓰므로 입찰 시장·배송 관제를 다른 탭에서 열어도 같은 시연 상태를 본다. */
export async function fakeLogisticsFetch(path: string, init: RequestInit = {}): Promise<Response> {
  init.signal?.throwIfAborted();
  const store = new FakeLogisticsStore(load() ?? memory);
  const body = typeof init.body === "string" && init.body ? JSON.parse(init.body) : undefined;
  const response = store.handle((init.method ?? "GET").toUpperCase(), path, body);
  memory = store.state;
  try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store.state)); } catch { /* 저장 불가 시 탭 메모리로 유지 */ }
  return response;
}
