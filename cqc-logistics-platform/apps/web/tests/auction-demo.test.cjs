/* eslint-disable @typescript-eslint/no-require-imports -- 테스트용 타입스크립트 로더 */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const ts = require("typescript");
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, filename);
const { collectBatches, advanceTask } = require("../src/lib/auction-demo.ts");
const { step, initialRuntime } = require("../src/lib/quality-runtime.ts");
const { sampleApples } = require("../src/lib/sample-apples.ts");
const base = Date.parse("2026-09-29T00:00:00Z");
const result = step(step(initialRuntime(), base), base + 1000).history[0];
const rows = Array.from({ length: 4 }, (_, i) => ({ ...result, id: `APPLE-${i}` }));
test("분류별 통과 4개 누적 및 중복·검수·오류 제외", () => {
  const seen = new Set(), buckets = new Map();
  const bad = [{ ...result, id: "review", reviewRequired: true }, { ...result, id: "error", excluded: true }, { ...result, id: "failed", control: "NO_RESPONSE" }];
  assert.equal(collectBatches([...rows.slice(0, 2), ...bad], seen, buckets).length, 0);
  assert.equal(collectBatches(rows, seen, buckets).length, 1);
  assert.equal(collectBatches(rows, seen, buckets).length, 0);
  assert.equal(buckets.size, 0);
});
test("당도 구간과 품종·등급을 섞지 않음", () => {
  const split = rows.map((row, i) => ({ ...row, bin: i % 2 ? "DEMO_BIN_01" : "DEMO_BIN_02" }));
  const buckets = new Map();
  assert.equal(collectBatches(split, new Set(), buckets).length, 0);
  assert.equal(buckets.size, 2);
});
test("500ms 재생은 초당 2개이고 통계는 초 단위로 합침", () => {
  let state = initialRuntime();
  for (let i = 0; i < 8; i++) state = step(state, base + i * 500, 500);
  assert.equal(state.sequence, 8);
  assert.equal(state.today.total, 7);
  assert.equal(state.throughput, 2);
  assert.equal(new Set(state.points.map((p) => p.at)).size, state.points.length);
  assert.equal(state.points.at(-1).count, 2);
  let parallel = { ...initialRuntime(), concurrency: 4 };
  for (let i = 0; i < 8; i++) parallel = step(parallel, base + i * 500, 500);
  assert.equal(parallel.sequence, 8);
});
test("모든 시연 사과는 실제 12장의 독립 파일을 제공", () => {
  for (const apple of sampleApples) {
    assert.equal(apple.images.length, 12);
    assert.equal(new Set(apple.images).size, 12);
    for (const image of apple.images) assert.ok(fs.existsSync(`${__dirname}/../public${image}`));
  }
});
function server() {
  const lots = [], bids = [], orders = [], calls = [];
  const api = async (path, body) => {
    calls.push([path, body]);
    if (path === "/cqc-results") return body;
    if (path === "/lots") { if (!body) return lots; const lot = { lotId: "LOT-1", cqcId: body.cqcId, auctionStatus: "DRAFT" }; lots.push(lot); return lot; }
    if (path.endsWith("/open")) { lots[0].auctionStatus = "OPEN"; return lots[0]; }
    if (path.endsWith("/bids")) { if (body) bids.push(body); return body ?? bids; }
    if (path === "/control/overview") return { orders };
    if (path.endsWith("/close")) { lots[0].auctionStatus = "AWARDED"; const order = { orderId: "ORDER-1", lotId: "LOT-1", status: "MATCHED" }; orders.push(order); return { order }; }
    if (path.endsWith("/dispatch")) { orders[0].status = "ASSIGNED"; return { order: orders[0] }; }
    if (path === "/orders/ORDER-1") return orders[0];
    throw new Error(path);
  };
  return { api, lots, bids, orders, calls };
}
test("자동 출품→입찰 3회→낙찰→배차 및 응답 유실 단계 재시도", async () => {
  const s = server();
  const task = { cqcId: "FE-DEMO-1", batch: { key: "bin", rows }, stage: 0, bidCount: 0 };
  for (let i = 0; i < 3; i++) await advanceTask(task, s.api, base + i * 1500);
  task.stage = 1;
  await advanceTask(task, s.api, base + 4500);
  assert.equal(s.lots.length, 1);
  await advanceTask(task, s.api, base + 6000);
  for (let i = 0; i < 3; i++) await advanceTask(task, s.api, base + 7500 + i * 1500);
  task.bidCount = 2;
  await advanceTask(task, s.api, base + 12000);
  assert.equal(s.bids.length, 3);
  await advanceTask(task, s.api, base + 20000);
  await advanceTask(task, s.api, base + 21500);
  task.stage = 4;
  await advanceTask(task, s.api, base + 23000);
  assert.equal(s.orders.length, 1);
  await advanceTask(task, s.api, base + 24500);
  task.stage = 5;
  await advanceTask(task, s.api, base + 26000);
  assert.equal(s.calls.filter(([path]) => path.endsWith("/dispatch")).length, 1);
  assert.equal(task.stage, 6);
});
test("가용 차량 오류는 배차 완료로 기록하지 않고 재개 가능", async () => {
  const task = { cqcId: "test", batch: { key: "bin", rows }, stage: 5, bidCount: 3, orderId: "ORDER-1", lotId: "LOT-1" };
  const api = async (path) => { if (path.endsWith("/dispatch")) throw new Error("가용 차량 없음"); return { status: "MATCHED" }; };
  await assert.rejects(advanceTask(task, api, base), /가용 차량/);
  assert.equal(task.stage, 5);
});
test("입찰 없이 수동 마감된 시연 출품은 배차하지 않음", async () => {
  const s = server();
  s.lots.push({ lotId: "LOT-1", cqcId: "test", auctionStatus: "CLOSED_UNSOLD" });
  const task = { cqcId: "test", batch: { key: "bin", rows }, stage: 4, bidCount: 0, lotId: "LOT-1" };
  await advanceTask(task, s.api, base);
  assert.equal(task.stage, 6);
  assert.equal(s.orders.length, 0);
});
