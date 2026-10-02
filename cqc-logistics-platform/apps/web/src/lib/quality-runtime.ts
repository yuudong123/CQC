import {
  MOCK_INSPECTIONS,
  type InspectionRecord,
  type MisclassificationType,
} from "./quality-contract";
import { sampleApples } from "./sample-apples";

export const FAULTS = {
  INFERENCE_TIMEOUT: "추론 시간 초과",
  INFERENCE_ERROR: "추론 오류",
  DB_ERROR: "DB 저장 오류",
  CONTROL_REJECTED: "명령 거부",
  CONTROL_NO_RESPONSE: "제어 무응답",
  CONTROL_FAILED: "제어 실패",
} as const;
export type Fault = keyof typeof FAULTS;
export type Scope = "ALL" | "NEXT";
export type Job = {
  id: string;
  index: number;
  started: number;
  finish: number;
  faults: Fault[];
  previewUrl?: string;
};
export type Result = InspectionRecord & {
  inferenceMs: number | null;
  cultivarConfidence: number | null;
  modelVersion: string | null;
  reviewRequired: boolean;
  previewUrl?: string;
  timestamp: number;
  excluded: boolean;
  control: "NOT_REQUESTED" | "SUCCEEDED" | "FALLBACK" | "NO_RESPONSE" | "REJECTED" | "FAILED";
  persistence: "SAVED" | "FAILED";
  faults: Fault[];
};
export type Point = {
  at: number;
  count: number;
  review: number;
  excluded: number;
};
export type Runtime = {
  throughput: number;
  running: boolean;
  concurrency?: number;
  /** 사과 묶음 투입 시작 간격(라인 속도). 서버가 제공하지 않으면 없다. */
  intervalMs?: number;
  sequence?: number;
  tick?: number;
  faults: Fault[];
  scope?: Scope;
  jobs: Job[];
  history: Result[];
  images: Result[];
  points: Point[];
  errors: Result[];
  today: {
    date: string;
    total: number;
    normal: number;
    review: number;
    excluded: number;
    grades: Record<string, number>;
    varieties: Record<string, number>;
    bins: Record<string, number>;
    reinspection: number;
    inferenceTotalMs: number;
    inferenceCount: number;
    suspicions: Record<Exclude<MisclassificationType, "NONE">, number>;
  };
  lastSaved: number | null;
  dbDown: boolean;
};
function emptyToday(date: string): Runtime["today"] {
  return {
    date,
    total: 0,
    normal: 0,
    review: 0,
    excluded: 0,
    grades: { 특: 0, 상: 0, 보통: 0 },
    varieties: { 부사: 0, 양광: 0 },
    bins: {},
    reinspection: 0,
    inferenceTotalMs: 0,
    inferenceCount: 0,
    suspicions: { CULTIVAR_SUSPECT: 0, QUALITY_SUSPECT: 0, OTHER: 0 },
  };
}
export function initialRuntime(): Runtime {
  return {
    throughput: 0,
    running: true,
    concurrency: 1,
    intervalMs: DEMO_INPUT_INTERVAL_MS,
    sequence: 0,
    tick: 0,
    faults: [],
    scope: "ALL",
    jobs: [],
    history: [],
    images: [],
    points: [],
    errors: [],
    today: emptyToday(""),
    lastSaved: null,
    dbDown: false,
  };
}
export function kst(now: number) {
  return new Date(now + 9 * 3600_000).toISOString();
}
export function imageIndexForJob(index: number) {
  const sample = MOCK_INSPECTIONS[index % MOCK_INSPECTIONS.length];
  return Math.max(0, sampleApples.findIndex((apple) => apple.variety === sample.variety && apple.grade === sample.grade));
}
// 브라우저 예시의 사과 그룹 투입 간격. 상용 광학 선별기는 레인당 초당 1~3개라 그 하한인 초당 1개로 둔다.
export const DEMO_INPUT_INTERVAL_MS = 1000;
/** 라인 속도 선택지. Backend `capabilities.intervals`와 같은 값이다. */
export const LINE_INTERVALS = [1000, 2000, 3000];
/** 진행 중인 마지막 1초 구간을 뺀 최근 `seconds`초의 초당 평균 처리량. 간격이 1초보다 길어도 0으로 떨어지지 않는다. */
export function recentThroughput(points: Point[], seconds = 10): number {
  const end = points.at(-1)?.at;
  if (end === undefined) return 0;
  const done = points.filter((point) => point.at >= end - seconds * 1000 && point.at < end);
  if (!done.length) return 0;
  const span = Math.min(seconds, Math.max(1, (end - Math.min(...done.map((point) => point.at))) / 1000));
  return done.reduce((sum, point) => sum + point.count, 0) / span;
}
export function step(state: Runtime, now: number, intervalMs = 1000, singleInput = false): Runtime {
  const date = kst(now).slice(0, 10);
  const next: Runtime = {
    ...state,
    tick: (state.tick ?? 0) + 1,
    jobs: state.jobs.filter((job) => job.finish > now),
    today:
      date === state.today.date
        ? {
            ...state.today,
            grades: { ...state.today.grades },
            varieties: { ...state.today.varieties },
            bins: { ...state.today.bins },
            suspicions: { ...state.today.suspicions },
          }
        : emptyToday(date),
  };
  const done = state.jobs
    .filter((job) => job.finish <= now)
    .map((job) => {
      const sample = MOCK_INSPECTIONS[job.index % MOCK_INSPECTIONS.length];
      const timeout = job.faults.includes("INFERENCE_TIMEOUT"),
        inferenceError = job.faults.includes("INFERENCE_ERROR");
      const excluded = timeout || inferenceError;
      const review = excluded || job.index % 7 === 3;
      const rejected = job.faults.includes("CONTROL_REJECTED"),
        noResponse = job.faults.includes("CONTROL_NO_RESPONSE");
      const controlFailed = job.faults.includes("CONTROL_FAILED");
      return {
        ...sample,
        imageIndex: imageIndexForJob(job.index),
        id: job.id,
        date,
        time: kst(now).slice(11, 23),
        timestamp: now,
        variety: excluded ? null : sample.variety,
        grade: excluded ? null : sample.grade,
        inferenceMs: excluded ? null : 300 + (job.index % 100),
        cultivarConfidence: excluded ? null : 95.4,
        modelVersion: excluded ? null : "reference-only",
        reviewRequired: review || rejected || noResponse || controlFailed,
        status: excluded ? "FAIL" : review ? "REVIEW" : "PASS",
        processingStatus: timeout
          ? "TIMEOUT"
          : inferenceError
            ? "ERROR"
            : "COMPLETED",
        confidence: excluded ? null : review ? 42 : 94.2,
        errorCode: job.faults[0] ?? "NONE",
        misclassification: "NONE",
        bin: noResponse || controlFailed
          ? "전송 실패"
          : review || rejected
            ? "TEST_REINSPECTION_BIN"
            : `DEMO_BIN_${String((sample.variety === "양광" ? 6 : 0) + ["특", "상", "보통"].indexOf(sample.grade!) * 2 + (sample.virtualBrix! >= 14 ? 2 : 1)).padStart(2, "0")}`,
        excluded,
        control: controlFailed
          ? "FAILED"
          : noResponse
          ? "NO_RESPONSE"
          : rejected
            ? review
              ? "REJECTED"
              : "FALLBACK"
            : "SUCCEEDED",
        persistence: job.faults.includes("DB_ERROR") ? "FAILED" : "SAVED",
        faults: job.faults,
      } as Result;
    });
  next.throughput = done.length * (1000 / intervalMs);
  const saved = done.filter((row) => row.persistence === "SAVED");
  next.dbDown =
    state.faults.includes("DB_ERROR") ||
    done.some((row) => row.persistence === "FAILED");
  for (const row of saved) {
    next.today.total++;
    if (row.reviewRequired) next.today.reinspection++;
    if (row.inferenceMs !== null) {
      next.today.inferenceTotalMs += row.inferenceMs;
      next.today.inferenceCount++;
    }
    if (row.control === "SUCCEEDED" || row.control === "FALLBACK")
      next.today.bins[row.bin] = (next.today.bins[row.bin] ?? 0) + 1;
    if (row.excluded) next.today.excluded++;
    else {
      next.today.normal++;
      if (row.grade)
        next.today.grades[row.grade] = (next.today.grades[row.grade] ?? 0) + 1;
      if (row.variety)
        next.today.varieties[row.variety] =
          (next.today.varieties[row.variety] ?? 0) + 1;
      if (row.status === "REVIEW") next.today.review++;
    }
  }
  if (saved.length) next.lastSaved = now;
  next.history = [...saved.reverse(), ...state.history].slice(0, 2000);
  next.images = [
    ...done.filter((row) => row.faults.length).reverse(),
    ...state.images,
  ].slice(0, 100);
  next.errors = [
    ...done.filter((row) => row.faults.length).reverse(),
    ...state.errors,
  ].slice(0, 50);
  const bucket = Math.floor(now / 1000) * 1000;
  const previous = state.points.at(-1)?.at === bucket ? state.points.at(-1) : undefined;
  next.points = next.dbDown
    ? state.points
    : [
        ...(previous ? state.points.slice(0, -1) : state.points),
        {
          at: bucket,
          count: saved.length + (previous?.count ?? 0),
          review: saved.filter((row) => row.status === "REVIEW").length + (previous?.review ?? 0),
          excluded: saved.filter((row) => row.excluded).length + (previous?.excluded ?? 0),
        },
      ].slice(-1800);
  if (state.running) {
    while (next.jobs.length < (state.concurrency ?? 0)) {
      const index = next.sequence ?? 0;
      next.sequence = index + 1;
      next.jobs.push({
        id: `DEMO-${String(index + 1).padStart(6, "0")}`,
        index,
        started: now,
        finish: now + intervalMs - 100,
        faults: [...next.faults],
      });
      if (next.scope === "NEXT") next.faults = [];
      // 병렬 슬롯을 늘려도 브라우저 예시는 한 번에 사과 한 그룹만 투입합니다.
      if (singleInput) break;
    }
  }
  return next;
}
/**
 * Backend 기본 신뢰도 기준(%, `src/api/core/config.py`). snapshot 이력에 판정 사유가 없어
 * 화면에서 같은 기준으로 재검사 사유를 만든다. Backend가 사유를 내려주면 그걸 쓴다(#55).
 */
export const CONFIDENCE_MIN = { cultivar: 50, quality: 60 } as const;
export type Exception = {
  kind: "reinspection" | "error";
  reason: string;
  lowCultivar: boolean;
  lowQuality: boolean;
};
/** 사람이 다시 봐야 하는 사과(재검사·오류)만 사유와 함께 돌려주고, 정상 통과는 null. */
export function exceptionOf(row: Result): Exception | null {
  if (row.excluded) {
    const reason =
      row.errorCode !== "NONE"
        ? FAULTS[row.errorCode]
        : row.processingStatus === "TIMEOUT"
          ? FAULTS.INFERENCE_TIMEOUT
          : FAULTS.INFERENCE_ERROR;
    return { kind: "error", reason, lowCultivar: false, lowQuality: false };
  }
  if (!row.reviewRequired) return null;
  const lowCultivar =
    row.cultivarConfidence !== null && row.cultivarConfidence < CONFIDENCE_MIN.cultivar;
  const lowQuality =
    row.confidence !== null && row.confidence < CONFIDENCE_MIN.quality;
  const reason =
    lowCultivar && lowQuality
      ? "품종·품질 신뢰도 미달"
      : lowCultivar
        ? "품종 신뢰도 미달"
        : lowQuality
          ? "품질 신뢰도 미달"
          : row.control === "FALLBACK"
            ? "제어 실패 · 재검사 대체"
            : "재검사 지정";
  return { kind: "reinspection", reason, lowCultivar, lowQuality };
}
export type ThroughputPoint = { at: number; value: number | null };
/**
 * `end`까지 최근 `minutes`분 처리량(건/초)을 `stepSeconds`마다 직전 `windowSeconds`초 이동평균으로 만든다.
 * 서버 points는 30초치뿐이라 저장 이력 시각으로 계산한다. 이력이 상한(`cap`)에 닿았으면
 * 가장 오래된 기록보다 앞선 창은 0이 아니라 수집 전(null)이다.
 */
export function throughputSeries(
  history: Result[],
  end: number,
  minutes = 5,
  windowSeconds = 20,
  stepSeconds = 2,
  cap = Infinity,
): ThroughputPoint[] {
  const times = history.map((row) => row.timestamp);
  const oldest = history.length >= cap ? Math.min(...times) : -Infinity;
  const total = Math.round((minutes * 60) / stepSeconds);
  return Array.from({ length: total + 1 }, (_, index) => {
    const at = end - (total - index) * stepSeconds * 1000;
    const from = at - windowSeconds * 1000;
    if (from < oldest) return { at, value: null };
    const count = times.filter((time) => time > from && time <= at).length;
    return { at, value: count / windowSeconds };
  });
}
export function periodPoints(points: Point[], minutes: number, now: number) {
  return points.filter((point) => point.at > now - minutes * 60_000);
}
export function csvCell(value: unknown) {
  const text = String(value ?? "");
  return `"${(/^[=+@\-\t\r]/.test(text) ? "'" + text : text).replaceAll('"', '""')}"`;
}

/** Edit only the review marker; inspection, bin and control results stay fixed. */
export function classifyResult(
  state: Runtime,
  id: string,
  value: MisclassificationType,
): Runtime {
  const record =
    state.history.find((row) => row.id === id) ??
    state.images.find((row) => row.id === id);
  if (!record || record.misclassification === value) return state;
  const suspicions = { ...state.today.suspicions };
  if (record.persistence === "SAVED" && record.date === state.today.date) {
    if (record.misclassification !== "NONE")
      suspicions[record.misclassification]--;
    if (value !== "NONE") suspicions[value]++;
  }
  const replace = (row: Result) =>
    row.id === id ? { ...row, misclassification: value } : row;
  return {
    ...state,
    today: { ...state.today, suspicions },
    history: state.history.map(replace),
    images: state.images.map(replace),
  };
}
