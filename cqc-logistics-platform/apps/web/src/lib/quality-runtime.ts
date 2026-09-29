import {
  MOCK_INSPECTIONS,
  type InspectionRecord,
  type MisclassificationType,
} from "./quality-contract";

export const FAULTS = {
  INFERENCE_TIMEOUT: "추론 시간 초과",
  INFERENCE_ERROR: "추론 오류",
  DB_ERROR: "DB 저장 오류",
  CONTROL_REJECTED: "명령 거부",
  CONTROL_NO_RESPONSE: "제어 무응답",
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
  control: "SUCCEEDED" | "FALLBACK" | "NO_RESPONSE" | "REJECTED";
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
  concurrency: number;
  sequence: number;
  tick: number;
  faults: Fault[];
  scope: Scope;
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
export function step(state: Runtime, now: number): Runtime {
  const date = kst(now).slice(0, 10);
  const next: Runtime = {
    ...state,
    tick: state.tick + 1,
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
      return {
        ...sample,
        id: job.id,
        date,
        time: kst(now).slice(11, 23),
        timestamp: now,
        variety: excluded ? null : sample.variety,
        grade: excluded ? null : sample.grade,
        inferenceMs: excluded ? null : 300 + (job.index % 100),
        cultivarConfidence: excluded ? null : 95.4,
        modelVersion: excluded ? null : "reference-only",
        reviewRequired: review || rejected || noResponse,
        status: excluded ? "FAIL" : review ? "REVIEW" : "PASS",
        processingStatus: timeout
          ? "TIMEOUT"
          : inferenceError
            ? "ERROR"
            : "COMPLETED",
        confidence: excluded ? null : review ? 42 : 94.2,
        errorCode: job.faults[0] ?? "NONE",
        misclassification: "NONE",
        bin: noResponse
          ? "전송 실패"
          : review || rejected
            ? "TEST_REINSPECTION_BIN"
            : `DEMO_BIN_${String((sample.variety === "양광" ? 6 : 0) + ["특", "상", "보통"].indexOf(sample.grade!) * 2 + (sample.virtualBrix! >= 14 ? 2 : 1)).padStart(2, "0")}`,
        excluded,
        control: noResponse
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
  next.throughput = done.length;
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
  next.points = next.dbDown
    ? state.points
    : [
        ...state.points,
        {
          at: Math.floor(now / 1000) * 1000,
          count: saved.length,
          review: saved.filter((row) => row.status === "REVIEW").length,
          excluded: saved.filter((row) => row.excluded).length,
        },
      ].slice(-1800);
  if (state.running) {
    while (next.jobs.length < state.concurrency) {
      const index = next.sequence++;
      next.jobs.push({
        id: `DEMO-${String(index + 1).padStart(6, "0")}`,
        index,
        started: now,
        finish: now + 900,
        faults: [...next.faults],
      });
      if (next.scope === "NEXT") next.faults = [];
    }
  }
  return next;
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
