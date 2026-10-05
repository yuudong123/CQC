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
  throughputSeries,
  exceptionOf,
  displayedJobs,
  nextPollDelay,
  POLL_INTERVAL_MS,
  DEMO_INPUT_INTERVAL_MS,
} = require("../src/lib/quality-runtime.ts");
const { parseFaultImages, imageCategory, imageReason, imageEvidence } = require("../src/lib/quality-fault-images.ts");
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
test("throughput series is a moving average over saved history and leaves uncollected spans empty", () => {
  // 2초 간격 투입 5분: 20초 창에는 10건 → 0.5건/초
  const history = Array.from({ length: 150 }, (_, i) => ({ timestamp: start + 300_000 - i * 2000 }));
  const series = throughputSeries(history, start + 300_000);
  assert.equal(series.length, 151);
  assert.equal(series.at(-1).at, start + 300_000);
  assert.equal(series.at(-1).value, 0.5);
  // 투입이 멈춘 구간은 0
  assert.equal(throughputSeries(history, start + 400_000).at(-1).value, 0);
  // 이력이 상한에 닿으면 가장 오래된 기록보다 앞선 창은 null
  const capped = throughputSeries(history.slice(0, 50), start + 300_000, 5, 20, 2, 50);
  assert.equal(capped[0].value, null);
  assert.equal(capped.at(-1).value, 0.5);
});
test("exceptions keep only reinspection and error rows with a reason", () => {
  const base = { excluded: false, reviewRequired: false, errorCode: "NONE", processingStatus: "COMPLETED", cultivarConfidence: 100, confidence: 99, control: "SUCCEEDED" };
  assert.equal(exceptionOf(base), null);
  assert.deepEqual(exceptionOf({ ...base, reviewRequired: true, confidence: 55.8 }), { kind: "reinspection", reason: "품질 신뢰도 미달", lowCultivar: false, lowQuality: true });
  assert.equal(exceptionOf({ ...base, reviewRequired: true, cultivarConfidence: 49.9 }).reason, "품종 신뢰도 미달");
  assert.equal(exceptionOf({ ...base, reviewRequired: true, cultivarConfidence: 40, confidence: 40 }).reason, "품종·품질 신뢰도 미달");
  // 기준값과 같으면 미달이 아니다
  assert.equal(exceptionOf({ ...base, reviewRequired: true, cultivarConfidence: 50, confidence: 60, control: "FALLBACK" }).reason, "제어 실패 · 재검사 대체");
  assert.deepEqual(exceptionOf({ ...base, excluded: true, errorCode: "INFERENCE_TIMEOUT", confidence: null }), { kind: "error", reason: "추론 시간 초과", lowCultivar: false, lowQuality: false });
  assert.equal(exceptionOf({ ...base, excluded: true, processingStatus: "ERROR" }).reason, "추론 오류");
});
test("job panel keeps the last apple until the next one starts", () => {
  const a = { id: "a", index: 1 };
  const b = { id: "b", index: 2 };
  // 처음부터 없으면 빈 칸
  assert.deepEqual(displayedJobs([], []), { jobs: [], held: false });
  // 처리 중이면 그대로
  assert.deepEqual(displayedJobs([a], []), { jobs: [a], held: false });
  // 끝나서 비면 마지막 사과를 남긴다
  assert.deepEqual(displayedJobs([], [a]), { jobs: [a], held: true });
  // 병렬로 여러 건이었으면 가장 나중 것 하나만
  assert.deepEqual(displayedJobs([], [a, b]), { jobs: [b], held: true });
  // 다음 사과가 들어오면 바로 바뀐다
  assert.deepEqual(displayedJobs([b], [a]), { jobs: [b], held: false });
});
test("polling keeps a fixed start-to-start interval", () => {
  assert.equal(POLL_INTERVAL_MS, 1000);
  // 응답 0.7초면 0.3초만 기다려 시작 간격 1초
  assert.equal(nextPollDelay(700), 300);
  assert.equal(nextPollDelay(0), 1000);
  // 응답이 주기보다 길면 바로 다시 조회
  assert.equal(nextPollDelay(1200), 0);
  // 시계가 뒤로 가도 주기보다 오래 기다리지 않음
  assert.equal(nextPollDelay(-50), 1000);
});
test("job panel follows recent completed apples it missed while processing", () => {
  const frames = [{ index: 0, previewUrl: "/api/quality/previews/live_x_00" }];
  const held = { id: "a", index: 1, started: 1000 };
  const done = (id, completedAt) => ({ id, status: "COMPLETED", completedAt, previewExpiresAt: completedAt + 3000, previews: frames });
  // 처리 중일 때 못 잡은 b가 a보다 나중에 끝났으면 b로 넘어간다
  const next = displayedJobs([], [held], [done("b", 3500)]);
  assert.equal(next.held, true);
  assert.equal(next.jobs[0].id, "b");
  assert.equal(next.jobs[0].previews, frames);
  // 이미 보여 준 a의 완료 기록이면 그대로 a
  assert.deepEqual(displayedJobs([], [held], [done("a", 1800)]), { jobs: [held], held: true });
  // a보다 먼저 끝난 옛 사과로는 돌아가지 않는다
  assert.deepEqual(displayedJobs([], [held], [done("z", 500)]), { jobs: [held], held: true });
  // 여러 건이면 가장 나중에 끝난 것
  assert.equal(displayedJobs([], [], [done("c", 4000), done("d", 4500)]).jobs[0].id, "d");
});
test("review images accept low confidence rows and legacy system errors", () => {
  const base = { id: "abc_00", inspectionId: "insp", imageIndex: 0, createdAt: 1, previewUrl: "/api/quality/previews/abc_00" };
  const low = { ...base, errorCode: null, category: "LOW_CONFIDENCE", decisionReason: "LOW_QUALITY_CONFIDENCE",
    cultivarConfidence: 0.99, qualityConfidence: 0.558, appliedCultivarThreshold: 0.5, appliedQualityThreshold: 0.6 };
  const legacy = { ...base, id: "def_01", previewUrl: "/api/quality/previews/def_01", errorCode: "INFERENCE_TIMEOUT" };
  const [l, g] = parseFaultImages({ items: [low, legacy] });
  assert.equal(imageCategory(l), "LOW_CONFIDENCE");
  assert.equal(imageReason(l), "품질 신뢰도 미달");
  assert.equal(imageEvidence(l), "품질 55.8% < 60.0%");
  // #90 이전 응답: category 없음 → 시스템 오류
  assert.equal(imageCategory(g), "SYSTEM_ERROR");
  assert.equal(imageReason(g), "추론 시간 초과");
  assert.equal(imageEvidence(g), "");
  // 오류 코드가 없는데 시스템 오류라고 하면 거부
  assert.throws(() => parseFaultImages({ items: [{ ...low, category: "SYSTEM_ERROR" }] }));
  assert.throws(() => parseFaultImages({ items: [{ ...low, qualityConfidence: 55.8 }] }));
});
