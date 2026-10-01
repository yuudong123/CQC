/* eslint-disable @typescript-eslint/no-require-imports -- Node test TypeScript loader. */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const ts = require("typescript");
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, filename);
const { QualityReferenceService } = require("../src/lib/quality-reference.ts");
const { parseSnapshot, parseHistory } = require("../src/lib/quality-api.ts");
const { proxyQuality } = require("../src/lib/quality-proxy.ts");
const { summarizeInspections } = require("../src/lib/quality-statistics.ts");
const { classifyResult } = require("../src/lib/quality-runtime.ts");
const openapi = require("../scripts/quality-openapi.cjs");
const Ajv = require("ajv");
const ajv = new Ajv({ allErrors: true, strict: false });
const validates = Object.fromEntries(["Snapshot", "HistoryPage", "Summary", "ReviewAck", "ImageDeleteAck", "FaultImages"].map(name => [name, ajv.compile({ $ref: `#/components/schemas/${name}`, components: openapi.components })]));
const start = Date.parse("2026-09-28T00:00:00Z");
function fixture() {
  let now = start;
  const service = new QualityReferenceService(() => now, async () => new Uint8Array([1, 2, 3]));
  const request = (path, method = "GET", body) => service.handle(new Request(`http://reference/v1/quality/${path}`, { method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) }));
  const tick = (count = 1) => { for (let i = 0; i < count; i++) { now += 1000; service.tick(); } };
  return { service, request, tick };
}
function schema(name, value) { assert.ok(validates[name](value), JSON.stringify(validates[name].errors)); return value; }
test("reference snapshot and OpenAPI match; invalid versions and malformed data fail closed", async () => {
  const f = fixture(); f.tick(3);
  const response = await f.request("snapshot");
  const value = schema("Snapshot", parseSnapshot(await response.json()));
  assert.equal(value.source, "reference");
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.throws(() => parseSnapshot({ ...value, contractVersion: "2" }));
  assert.throws(() => parseSnapshot({ ...value, state: { ...value.state, history: [{ id: "bad" }] } }));
  assert.throws(() => parseSnapshot({ ...value, state: { ...value.state, history: [{ ...value.state.history[0], previewUrl: "https://untrusted.test/image" }] } }));
});
test("history pagination stays anchored while new input arrives and CSV exports every match", async () => {
  const f = fixture(); f.tick(121);
  const first = schema("HistoryPage", parseHistory(await (await f.request("inspections?pageSize=50")).json()));
  assert.equal(first.total, 120); assert.equal(first.items.length, 50);
  f.tick(8);
  const second = parseHistory(await (await f.request(`inspections?page=2&pageSize=50&snapshotAt=${first.snapshotAt}`)).json());
  assert.equal(second.total, 120);
  assert.equal(new Set([...first.items, ...second.items].map(r => r.id)).size, 100);
  const csv = await (await f.request(`inspections.csv?pageSize=50&snapshotAt=${first.snapshotAt}`)).text();
  assert.equal(csv.split("\r\n").length, 121);
  assert.ok(!csv.includes("previewUrl")); assert.ok(!csv.includes("/apples/"));
});
test("backend snapshot may omit unavailable Simulator settings and history retention", async () => {
  const f = fixture(); f.tick(1);
  const snapshot = await (await f.request("snapshot")).json();
  const { concurrency, sequence, tick, scope, ...state } = snapshot.state;
  const { history, ...retention } = snapshot.retention;
  const backend = { ...snapshot, source: "backend", state, retention };
  schema("Snapshot", parseSnapshot(backend));
  assert.equal(backend.state.sequence, undefined);
  assert.equal(backend.retention.history, undefined);
});
test("snapshot accepts line speed settings and rejects malformed intervals", async () => {
  const f = fixture(); f.tick(1);
  const snapshot = await (await f.request("snapshot")).json();
  const withSpeed = { ...snapshot, capabilities: { ...snapshot.capabilities, intervals: [1000, 2000, 3000] }, state: { ...snapshot.state, intervalMs: 2000 } };
  assert.equal(parseSnapshot(withSpeed).state.intervalMs, 2000);
  assert.throws(() => parseSnapshot({ ...withSpeed, capabilities: { ...withSpeed.capabilities, intervals: ["2000"] } }));
  assert.throws(() => parseSnapshot({ ...withSpeed, state: { ...withSpeed.state, intervalMs: -1 } }));
});
test("history accepts unavailable image index and an explicit control failure", async () => {
  const f = fixture(); f.tick(2);
  const history = await (await f.request("inspections?pageSize=50")).json();
  const item = {
    ...history.items[0],
    imageIndex: null,
    control: "FAILED",
    errorCode: "CONTROL_FAILED",
    faults: ["CONTROL_FAILED"],
    reviewRequired: true,
    status: "REVIEW",
  };
  const value = parseHistory({ ...history, items: [item], total: 1 });
  schema("HistoryPage", value);
  assert.equal(value.items[0].imageIndex, null);
  assert.equal(value.items[0].control, "FAILED");
});
test("history accepts unattempted control without treating it as failure", async () => {
  const f = fixture(); f.tick(2);
  const history = await (await f.request("inspections?pageSize=50")).json();
  const item = { ...history.items[0], control: "NOT_REQUESTED", errorCode: "DB_ERROR", faults: ["DB_ERROR"] };
  const value = parseHistory({ ...history, items: [item], total: 1 });
  schema("HistoryPage", value);
  assert.equal(value.items[0].control, "NOT_REQUESTED");
});
test("invalid query, date order, enum and request bodies are rejected", async () => {
  const f = fixture();
  for (const query of ["from=2026-09-29&to=2026-09-28", "from=2026-02-31", "page=-1", "pageSize=1000", "variety=invalid", "unexpected=true"]) assert.equal((await f.request(`inspections?${query}`)).status, 422);
  assert.equal((await f.request("simulator", "PUT", { expectedRevision: 0, running: "yes" })).status, 422);
  assert.equal((await f.request("simulator", "PUT", { expectedRevision: 0, faults: ["INFERENCE_ERROR", "INFERENCE_ERROR"] })).status, 422);
});
test("revision prevents lost settings; next-one faults consumed exactly once across parallel workers", async () => {
  const f = fixture();
  assert.equal((await f.request("simulator", "PUT", { expectedRevision: 0, concurrency: 4, scope: "NEXT", faults: ["INFERENCE_TIMEOUT", "CONTROL_NO_RESPONSE"] })).status, 200);
  assert.equal((await f.request("simulator", "PUT", { expectedRevision: 0, running: false })).status, 409);
  f.tick(2);
  const value = schema("Snapshot", parseSnapshot(await (await f.request("snapshot")).json()));
  assert.equal(value.state.history.filter(r => r.excluded).length, 1);
  assert.equal(value.state.history.find(r => r.excluded).variety, null);
  assert.equal(value.state.history.find(r => r.excluded).confidence, null);
  assert.equal(value.state.faults.length, 0);
  assert.equal(value.revision, 2);
});
test("review markers replace and clear without altering physical decisions or double counting", async () => {
  const f = fixture(); f.tick(2);
  const row = f.service.state.history[0];
  const before = { bin: row.bin, status: row.status, control: row.control };
  for (const value of ["CULTIVAR_SUSPECT", "OTHER", "OTHER"]) schema("ReviewAck", await (await f.request(`inspections/${row.id}/review`, "PATCH", { misclassification: value })).json());
  assert.deepEqual(f.service.state.today.suspicions, { CULTIVAR_SUSPECT: 0, QUALITY_SUSPECT: 0, OTHER: 1 });
  const current = f.service.state.history[0];
  assert.deepEqual({ bin: current.bin, status: current.status, control: current.control }, before);
  await f.request(`inspections/${row.id}/review`, "PATCH", { misclassification: "NONE" });
  assert.equal(f.service.state.today.suspicions.OTHER, 0);
  assert.equal((await f.request(`inspections/${row.id}/review`, "PATCH", { misclassification: "LOW_CONFIDENCE" })).status, 422);
});
test("temporary preview expires after completion; image deletion preserves history and newer images", async () => {
  const f = fixture(); f.tick(); const id = f.service.state.jobs[0].id;
  assert.equal((await f.request(`previews/${id}`)).status, 200);
  f.tick(); assert.equal((await f.request(`previews/${id}`)).status, 410);
  f.service.state.faults = ["INFERENCE_ERROR"]; f.tick(2);
  const listed = schema("FaultImages", await (await f.request("fault-images")).json());
  const captured = listed.items.map(r => r.id); f.tick(2);
  const response = schema("ImageDeleteAck", await (await f.request("fault-images", "DELETE", { ids: captured })).json());
  assert.deepEqual(response.deletedIds, captured);
  assert.ok(f.service.state.images.length > 0);
  assert.ok(f.service.state.history.some(r => listed.items.some(image => image.inspectionId === r.id)));
  assert.equal((await f.request(`previews/${captured[0]}`)).status, 410);
});
test("DB outage rejects history/review but snapshot keeps saved totals and control remains available", async () => {
  const f = fixture(); f.tick(3); const total = f.service.state.today.total;
  f.service.state.faults = ["DB_ERROR"]; f.tick(2);
  assert.equal((await f.request("inspections")).status, 503);
  assert.equal((await f.request("statistics")).status, 503);
  const snapshot = parseSnapshot(await (await f.request("snapshot")).json());
  // One in-flight request admitted before DB failure can still complete normally.
  assert.equal(snapshot.state.today.total, total + 1);
  assert.equal(snapshot.state.errors[0].control, "SUCCEEDED");
  assert.equal((await f.request("simulator", "PUT", { expectedRevision: f.service.revision, running: false })).status, 200);
});
test("period statistics use saved records, include low confidence, exclude timeout predictions", async () => {
  const f = fixture(); f.tick(12);
  f.service.state.faults = ["INFERENCE_TIMEOUT"]; f.tick(3);
  const summary = schema("Summary", await (await f.request("statistics?from=2026-09-28&to=2026-09-28")).json());
  assert.deepEqual(summary, summarizeInspections(f.service.state.history));
  assert.equal(summary.total, summary.normal + summary.excluded);
  assert.ok(summary.reinspection > summary.excluded);
  assert.equal(summary.inferenceCount, summary.normal);
  const csv = await (await f.request("statistics.csv?from=2026-09-28&to=2026-09-28")).text();
  assert.ok(csv.includes("reinspection_ratio")); assert.ok(csv.includes("average_inference_ms"));
});
test("daily suspicion totals ignore older records and failed persistence", () => {
  const f = fixture(); f.tick(2);
  const row = f.service.state.history[0]; f.service.state.today.date = "2026-09-29";
  const changed = classifyResult(f.service.state, row.id, "OTHER");
  assert.equal(changed.today.suspicions.OTHER, 0);
});
test("proxy restricts routes, methods, origins, content types and sanitizes backend failures", async () => {
  const original = global.fetch, previous = process.env.CQC_QUALITY_BACKEND_URL;
  try {
    delete process.env.CQC_QUALITY_BACKEND_URL;
    const req = (method = "GET", origin) => new Request("http://localhost:3000/api/quality/snapshot", { method, headers: origin ? { origin } : {} });
    assert.equal((await proxyQuality(req(), "snapshot")).status, 503);
    process.env.CQC_QUALITY_BACKEND_URL = "http://backend:8000";
    assert.equal((await proxyQuality(req(), "../health")).status, 404);
    assert.equal((await proxyQuality(req("POST"), "snapshot")).status, 405);
    assert.equal((await proxyQuality(req("PUT", "http://other.test"), "simulator")).status, 403);
    global.fetch = async (url, options) => { assert.equal(String(url), "http://backend:8000/v1/quality/snapshot"); assert.equal(options.redirect, "error"); return Response.json({ safe: true }); };
    const ok = await proxyQuality(req(), "snapshot"); assert.equal(ok.status, 200); assert.equal(ok.headers.get("cache-control"), "no-store");
    global.fetch = async () => new Response("<html>private</html>", { headers: { "Content-Type": "text/html" } });
    assert.equal((await proxyQuality(req(), "snapshot")).status, 502);
    global.fetch = async () => { throw new Error("private internal address"); };
    const failed = await proxyQuality(req(), "snapshot"); assert.equal(failed.status, 503); assert.ok(!(await failed.text()).includes("private"));
  } finally { global.fetch = original; if (previous === undefined) delete process.env.CQC_QUALITY_BACKEND_URL; else process.env.CQC_QUALITY_BACKEND_URL = previous; }
});

const { parseFaultImages } = require("../src/lib/quality-fault-images.ts");
test("individual image IDs preserve sibling views and inspection records; retention counts files", async () => {
  const f = fixture(); f.service.state.faults = ["INFERENCE_ERROR"]; f.tick(2);
  const items = parseFaultImages(schema("FaultImages", await (await f.request("fault-images")).json()));
  assert.ok(items.length > 1);
  const first = items[0], sibling = items.find(r => r.inspectionId === first.inspectionId && r.id !== first.id);
  assert.ok(sibling); assert.notEqual(first.id, first.inspectionId);
  assert.deepEqual(await (await f.request("fault-images", "DELETE", { ids: [first.inspectionId] })).json(), { deletedIds: [] });
  const historyBefore = JSON.stringify(f.service.state.history);
  await f.request("fault-images", "DELETE", { ids: [first.id] });
  assert.equal((await f.request(`previews/${first.id}`)).status, 410);
  assert.equal((await f.request(`previews/${sibling.id}`)).status, 200);
  assert.equal(JSON.stringify(f.service.state.history), historyBefore);
  assert.equal(f.service.snapshot().retention.images, items.length - 1);
  f.tick(30);
  const retained = parseFaultImages(await (await f.request("fault-images")).json());
  assert.equal(retained.length, 100);
  assert.ok(!retained.some(r => r.id === sibling.id));
  assert.equal(f.service.snapshot().retention.images, 100);
  assert.ok(f.service.state.history.some(r => r.id === first.inspectionId));
  assert.throws(() => parseFaultImages({ items: [{ ...retained[0], imageIndex: 12 }] }));
  assert.throws(() => parseFaultImages({ items: [{ ...retained[0], previewUrl: `/api/quality/previews/${first.inspectionId}` }] }));
  assert.throws(() => parseFaultImages({ items: f.service.state.images }));
});

test("fault image reference response validates against the Backend-published OpenAPI", async () => {
  const published = JSON.parse(fs.readFileSync(require("node:path").resolve(__dirname, "../../../../docs/contracts/quality-operations.openapi.json"), "utf8"));
  const validate = ajv.compile({ $ref: "#/components/schemas/FaultImages", components: published.components });
  const f = fixture(); f.service.state.faults = ["INFERENCE_TIMEOUT"]; f.tick(2);
  const response = await (await f.request("fault-images")).json();
  assert.ok(response.items.length > 1);
  assert.ok(validate(response), JSON.stringify(validate.errors));
  assert.deepEqual(await (await f.request("fault-images", "DELETE", { ids: [] })).json(), { deletedIds: [] });
});

const { loadQualityPoll } = require("../src/lib/quality-fault-images.ts");
test("fault image inventory failure keeps the control snapshot; snapshot failure still fails the poll", async () => {
  const snapshot = { revision: 7 };
  const images = [{ id: "a_view_0" }];
  const ok = await loadQualityPoll(async () => snapshot, async () => images);
  assert.deepEqual(ok, { snapshot, images, imageError: "" });
  const unavailable = await loadQualityPoll(async () => snapshot, async () => { throw new Error("서비스에 연결할 수 없습니다."); });
  assert.equal(unavailable.snapshot, snapshot);
  assert.equal(unavailable.images, null);
  assert.match(unavailable.imageError, /장애 이미지 목록을 불러오지 못했습니다: 서비스에 연결할 수 없습니다\./);
  let imagesStarted = false;
  await assert.rejects(
    loadQualityPoll(async () => { throw new Error("snapshot down"); }, async () => { imagesStarted = true; return images; }),
    /snapshot down/,
  );
  assert.ok(imagesStarted, "both requests start in parallel");
});
