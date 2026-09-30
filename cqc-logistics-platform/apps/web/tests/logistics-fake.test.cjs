/* eslint-disable @typescript-eslint/no-require-imports -- Node test TypeScript loader. */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const ts = require("typescript");
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, filename);
const { FakeLogisticsStore, GATE_AUTO_COMPLETE_MS, fakeLogisticsFetch } = require("../src/lib/logistics-fake.ts");
const { advanceTask } = require("../src/lib/auction-demo.ts");

function fixture() {
  let now = Date.parse("2026-10-01T01:00:00Z");
  const store = new FakeLogisticsStore(undefined, () => now);
  const call = async (method, path, body) => {
    const response = store.handle(method, path, body);
    return { status: response.status, body: await response.json() };
  };
  return { store, call, advance: (ms) => { now += ms; }, now: () => now };
}

test("시드 상태는 apps/api 발표 초기 상태와 같다", async () => {
  const { call } = fixture();
  const overview = (await call("GET", "/control/overview")).body;
  assert.equal(overview.fleets.length, 3);
  assert.deepEqual(overview.fleets.map((fleet) => fleet.name), ["CQC-01", "CQC-02", "CQC-03"]);
  assert.equal(overview.fleets[0].status, "TO_PICKUP");
  assert.equal(overview.stats.openAuctions, 1);
  assert.equal(overview.stats.activeFleets, 1);
  assert.equal(overview.stats.inTransitOrders, 1);
  assert.equal(overview.routes[0].stops.length, 2);
  const open = (await call("GET", "/lots?auction_status=OPEN")).body;
  assert.equal(open.length, 1);
  assert.equal(open[0].reservePriceWon, 1_200_000);
});

test("출품→입찰→낙찰→배차 흐름과 오류 메시지가 실제 API와 같다", async () => {
  const { call } = fixture();
  await call("POST", "/cqc-results", { cqcId: "c1", farmId: "farm", variety: "fuji", qualityGrade: "SPECIAL", confidence: 0.9, quantityKg: 1, origin: { type: "Point", coordinates: [127.004, 36.789] } });
  assert.equal((await call("POST", "/lots", { cqcId: "missing", reservePriceWon: 5000 })).status, 404);
  const lot = (await call("POST", "/lots", { cqcId: "c1", reservePriceWon: 5000 })).body;
  assert.equal(lot.auctionStatus, "DRAFT");
  assert.equal((await call("POST", `/lots/${lot.lotId}/bids`, { buyerId: "b", priceWon: 6000 })).body.detail, "진행 중인 경매가 아닙니다.");
  await call("POST", `/lots/${lot.lotId}/open`, {});
  assert.equal((await call("POST", `/lots/${lot.lotId}/open`, {})).status, 409);
  assert.equal((await call("POST", `/lots/${lot.lotId}/bids`, { buyerId: "b", priceWon: 4000 })).body.detail, "최저 낙찰가보다 낮은 입찰입니다.");
  assert.equal((await call("POST", `/lots/${lot.lotId}/bids`, { buyerId: "b1", priceWon: 5500, destination: { type: "Point", coordinates: [127.03, 37.5] } })).status, 201);
  assert.equal((await call("POST", `/lots/${lot.lotId}/bids`, { buyerId: "b2", priceWon: 5500 })).body.detail, "현재 최고 입찰가보다 높아야 합니다.");
  await call("POST", `/lots/${lot.lotId}/bids`, { buyerId: "b2", priceWon: 6000, destination: { type: "Point", coordinates: [127.03, 37.5] } });
  const bids = (await call("GET", `/lots/${lot.lotId}/bids`)).body;
  assert.deepEqual(bids.map((bid) => bid.priceWon), [6000, 5500]);
  const closed = (await call("POST", `/lots/${lot.lotId}/close`, {})).body;
  assert.equal(closed.lot.auctionStatus, "AWARDED");
  assert.equal(closed.winningBid.buyerId, "b2");
  assert.equal(closed.order.status, "MATCHED");
  const dispatched = (await call("POST", `/orders/${closed.order.orderId}/dispatch`, {})).body;
  assert.equal(dispatched.order.status, "ASSIGNED");
  assert.notEqual(dispatched.fleet.name, "CQC-01", "유휴 차량이 있으면 유휴 차량에 배차한다");
  assert.equal((await call("POST", `/orders/${closed.order.orderId}/dispatch`, {})).body.detail, "이미 배차된 주문입니다.");
  assert.equal((await call("GET", "/nope")).status, 404);
});

test("차량 이동·도착 후 상차·하차 자동 확인·고장 대체배차·초기화", async () => {
  const { store, call, advance } = fixture();
  const cqc01 = Object.values(store.state.fleets).find((fleet) => fleet.name === "CQC-01");
  const step = await call("POST", `/fleets/${cqc01.fleetId}/simulate-step`, {});
  assert.equal(step.body.arrived, true, "CQC-01은 픽업지 위에서 시작한다");
  assert.equal((await call("GET", "/control/overview")).body.alerts[0].title, "상차 확인 필요");
  advance(GATE_AUTO_COMPLETE_MS);
  const loaded = (await call("GET", "/control/overview")).body;
  assert.equal(loaded.fleets.find((fleet) => fleet.name === "CQC-01").status, "IN_TRANSIT");
  for (let i = 0; i < 5; i++) await call("POST", `/fleets/${cqc01.fleetId}/simulate-step`, {});
  advance(GATE_AUTO_COMPLETE_MS);
  const delivered = (await call("GET", "/control/overview")).body;
  assert.equal(delivered.fleets.find((fleet) => fleet.name === "CQC-01").status, "IDLE");
  assert.equal(delivered.orders[0].status, "DELIVERED");
  assert.equal(delivered.stats.inTransitOrders, 0);

  await call("POST", "/control/seed-reset", {});
  const fresh = Object.values(store.state.fleets).find((fleet) => fleet.name === "CQC-01");
  const broken = (await call("POST", `/fleets/${fresh.fleetId}/breakdown`, {})).body;
  assert.equal(broken.brokenFleet.status, "OUT_OF_SERVICE");
  assert.equal(broken.replacementFleet.name, "CQC-03", "남은 경유지에 가장 가까운 유휴 차량");
  assert.equal((await call("POST", `/fleets/${fresh.fleetId}/breakdown`, {})).body.detail, "이미 고장 처리된 차량입니다.");
  assert.equal((await call("GET", "/control/overview")).body.alerts.find((alert) => alert.severity === "CRITICAL").title, "차량 고장 격리");
});

test("자동 경매 시연 6단계가 가상 물류로 끝까지 진행된다", async () => {
  const { store, advance, now } = fixture();
  const api = async (path, body) => {
    const response = store.handle(body === undefined ? "GET" : "POST", path, body);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail);
    return data;
  };
  const row = { id: "i1", variety: "부사", grade: "특", confidence: 97, modelVersion: "v2", virtualBrix: 15, bin: "DEMO_BIN_02" };
  const task = { cqcId: "FE-DEMO-s-0", batch: { key: "k", rows: [row, row, row, row] }, stage: 0, bidCount: 0 };
  const messages = [];
  for (let i = 0; i < 20 && task.stage < 6; i++) { messages.push(await advanceTask(task, api, now())); advance(2000); }
  assert.equal(task.stage, 6);
  assert.ok(messages.some((message) => message.includes("자동 배차 완료")), messages.join(" / "));
  assert.equal(store.state.orders[task.orderId].status, "ASSIGNED");
});

test("fetch 대체 함수는 저장소가 없어도 Response를 돌려준다", async () => {
  const response = await fakeLogisticsFetch("/control/overview");
  assert.equal(response.status, 200);
  assert.equal((await response.json()).storage, "browser-demo");
  const created = await fakeLogisticsFetch("/cqc-results", { method: "POST", body: JSON.stringify({ cqcId: "x", farmId: "f", variety: "fuji", qualityGrade: "SPECIAL", confidence: 1, quantityKg: 1, origin: { type: "Point", coordinates: [127, 36] } }) });
  assert.equal(created.status, 201);
  const lots = await fakeLogisticsFetch("/lots", { method: "POST", body: JSON.stringify({ cqcId: "x", reservePriceWon: 5000 }) });
  assert.equal(lots.status, 201, "같은 탭 메모리 상태가 요청 사이에 유지된다");
});
