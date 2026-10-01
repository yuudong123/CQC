/* eslint-disable @typescript-eslint/no-require-imports -- Node test-only TypeScript CommonJS loader. */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const ts = require("typescript");
require.extensions[".ts"] = (module, filename) => {
  module._compile(
    ts.transpileModule(fs.readFileSync(filename, "utf8"), {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
      },
    }).outputText,
    filename,
  );
};
const {
  initialRuntime,
  step,
  periodPoints,
  csvCell,
  recentThroughput,
  DEMO_INPUT_INTERVAL_MS,
} = require("../src/lib/quality-runtime.ts");
const start = Date.parse("2026-09-28T00:00:00Z");
function complete(overrides = {}) {
  return step(step({ ...initialRuntime(), ...overrides }, start), start + 1000);
}

test("default ON; stop drains in-flight jobs; resume continues sequence", () => {
  const active = step(initialRuntime(), start);
  const stopped = step({ ...active, running: false }, start + 1000);
  assert.equal(stopped.jobs.length, 0);
  assert.equal(stopped.history.length, 1);
  const resumed = step({ ...stopped, running: true }, start + 2000);
  assert.equal(resumed.jobs[0].id, "DEMO-000002");
});
test("parallel slots and next-one faults apply to exactly one admitted job", () => {
  const state = complete({
    concurrency: 4,
    scope: "NEXT",
    faults: ["INFERENCE_TIMEOUT", "CONTROL_NO_RESPONSE"],
  });
  assert.equal(state.jobs.length, 4);
  assert.equal(state.faults.length, 0);
  assert.equal(state.history.filter((row) => row.excluded).length, 1);
  assert.equal(
    state.history.filter((row) => row.control === "NO_RESPONSE").length,
    1,
  );
  assert.equal(state.today.normal, 3);
  assert.equal(state.today.excluded, 1);
});
test("DB failure preserves normal routing, freezes saved totals and loses failed history", () => {
  const state = complete({ faults: ["DB_ERROR"] });
  assert.equal(state.today.total, 0);
  assert.equal(state.lastSaved, null);
  assert.equal(state.history.length, 0);
  assert.equal(state.errors[0].status, "PASS");
  assert.equal(state.errors[0].control, "SUCCEEDED");
  assert.match(state.errors[0].bin, /DEMO_BIN/);
  assert.equal(state.dbDown, true);
  let recovered = step({ ...state, faults: [] }, start + 2000);
  recovered = step(recovered, start + 3000);
  assert.equal(recovered.today.total, 1);
  assert.equal(recovered.history.length, 1);
});
test("low confidence counts in normal statistics; inference error does not", () => {
  const low = complete({ sequence: 3 });
  assert.equal(low.today.review, 1);
  assert.equal(low.today.normal, 1);
  assert.equal(low.history[0].status, "REVIEW");
  assert.equal(low.history[0].misclassification, "NONE");
  const error = complete({ faults: ["INFERENCE_ERROR"] });
  assert.equal(error.today.normal, 0);
  assert.equal(error.today.excluded, 1);
});
test("rejection uses fallback and no-response never claims success", () => {
  assert.equal(
    complete({ faults: ["CONTROL_REJECTED"] }).history[0].control,
    "FALLBACK",
  );
  assert.equal(
    complete({ faults: ["CONTROL_NO_RESPONSE"] }).history[0].bin,
    "전송 실패",
  );
});
test("12-bin mapping uses cultivar, grade and virtual sweetness", () => {
  const result = complete().history[0];
  assert.equal(result.bin, "DEMO_BIN_08");
});

test("14 Brix boundary matches display labels and inspection fixtures", () => {
  const { MOCK_INSPECTIONS } = require("../src/lib/quality-contract.ts");
  const { qualityBins } = require("../src/lib/quality-bins.ts");
  assert.deepEqual([...new Set(qualityBins.map((bin) => bin.sweetness))], [
    "14° 미만", "14° 이상",
  ]);
  for (const row of MOCK_INSPECTIONS.filter((row) => row.status === "PASS")) {
    const index = (row.variety === "양광" ? 6 : 0)
      + ["특", "상", "보통"].indexOf(row.grade) * 2
      + (row.virtualBrix >= 14 ? 2 : 1);
    assert.equal(row.bin, `DEMO_BIN_${String(index).padStart(2, "0")}`);
  }
  const original = MOCK_INSPECTIONS[0].virtualBrix;
  try {
    for (const [brix, bin] of [[12, "DEMO_BIN_07"], [13.9, "DEMO_BIN_07"], [14, "DEMO_BIN_08"]]) {
      MOCK_INSPECTIONS[0].virtualBrix = brix;
      assert.equal(complete().history[0].bin, bin);
    }
  } finally {
    MOCK_INSPECTIONS[0].virtualBrix = original;
  }
});
test("KST midnight resets daily counts; history remains", () => {
  const before = Date.parse("2026-09-28T14:59:58Z");
  let s = step(initialRuntime(), before);
  s = step(s, before + 1000);
  s = step(s, before + 2000);
  assert.equal(s.today.date, "2026-09-29");
  assert.equal(s.today.total, 1);
  assert.equal(s.history.length, 2);
});
test("8-hour accelerated run bounds all retained data", () => {
  let s = { ...initialRuntime(), concurrency: 4, faults: ["CONTROL_REJECTED"] };
  for (let i = 0; i < 28800; i++) s = step(s, start + i * 1000);
  assert.equal(s.history.length, 2000);
  assert.equal(s.images.length, 100);
  assert.equal(s.errors.length, 50);
  assert.equal(s.points.length, 1800);
  assert.equal(s.jobs.length, 4);
  assert.equal(periodPoints(s.points, 1, start + 28799 * 1000).length, 60);
  assert.equal(periodPoints(s.points, 30, start + 28799 * 1000).length, 1800);
  assert.equal(new Set(s.history.map((row) => row.id)).size, 2000);
});
test("CSV escapes quotes and guards spreadsheet formulas", () => {
  assert.equal(csvCell('a"b'), '"a""b"');
  assert.equal(csvCell("=1+1"), '"\'=1+1"');
});
test("recent throughput averages the last ten completed seconds", () => {
  const at = (s) => start + s * 1000;
  // 2초 간격 투입: 1초 단위로는 0과 1이 번갈아 나오지만 평균은 0.5건/초
  const every2s = Array.from({ length: 30 }, (_, i) => ({ at: at(i), count: i % 2 ? 0 : 1, review: 0, excluded: 0 }));
  assert.equal(recentThroughput(every2s), 0.5);
  // 진행 중인 마지막 구간은 빼고 계산
  const inProgress = [...every2s.slice(0, -1), { at: at(29), count: 5, review: 0, excluded: 0 }];
  assert.equal(recentThroughput(inProgress), 0.5);
  // 수집 구간이 짧으면 있는 구간으로 평균, 비어 있으면 0
  assert.equal(recentThroughput([{ at: at(0), count: 2, review: 0, excluded: 0 }, { at: at(2), count: 0, review: 0, excluded: 0 }]), 1);
  assert.equal(recentThroughput([]), 0);
});
test("demo runtime starts with the default line speed", () => {
  assert.equal(initialRuntime().intervalMs, DEMO_INPUT_INTERVAL_MS);
});
