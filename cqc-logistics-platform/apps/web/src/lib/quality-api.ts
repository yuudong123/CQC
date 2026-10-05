import {
  DEFAULT_QUALITY_FILTERS,
  ERROR_LABEL,
  type QualityFilterState,
  type MisclassificationType,
} from "./quality-contract";
import type { Runtime, Scope, Fault, Result } from "./quality-runtime";

/** Versioned operations read model. POST /v1/inspections keeps its existing schema. */
export type ComponentState = {
  status: "healthy" | "stopped" | "error" | "unknown";
  lastSeenAt: number | null;
  detail: string;
};
export type QualitySnapshot = {
  contractVersion: "1";
  source: "reference" | "backend";
  capturedAt: number;
  revision: number;
  capabilities: {
    control: boolean;
    faults: boolean;
    review: boolean;
    deleteImages: boolean;
    concurrency: number[];
    intervals?: number[];
  };
  components: Record<
    "Simulator" | "Inference" | "Backend" | "MySQL",
    ComponentState
  >;
  retention: { history?: number; images: number };
  periodTotals: Record<"1" | "5" | "10" | "30", number>;
  state: Runtime;
};
export type SimulatorChange = Partial<
  Pick<Runtime, "running" | "concurrency" | "intervalMs"> & { scope: Scope; faults: Fault[] }
>;
export type HistoryPage = {
  items: Result[];
  total: number;
  page: number;
  pageSize: number;
  snapshotAt: number;
  bins: string[];
};
export class QualityApiError extends Error {
  constructor(
    message: string,
    public status = 0,
  ) {
    super(message);
  }
}

const object = (v: unknown): v is Record<string, unknown> =>
  !!v && typeof v === "object" && !Array.isArray(v);
const finite = (v: unknown): v is number =>
  typeof v === "number" && Number.isFinite(v) && v >= 0;
const counts = (v: unknown) => object(v) && Object.values(v).every(finite);
const validResult = (v: unknown) => {
  if (!object(v)) return false;
  const prediction =
    v.excluded === true
      ? v.variety === null &&
        v.grade === null &&
        v.confidence === null &&
        v.cultivarConfidence === null &&
        v.inferenceMs === null
      : ["부사", "양광"].includes(String(v.variety)) &&
        ["특", "상", "보통"].includes(String(v.grade)) &&
        finite(v.confidence) &&
        v.confidence <= 100 &&
        finite(v.cultivarConfidence) &&
        v.cultivarConfidence <= 100;
  return (
    prediction &&
    typeof v.id === "string" &&
    /^[A-Za-z0-9_-]+$/.test(v.id) &&
    typeof v.date === "string" &&
    typeof v.time === "string" &&
    finite(v.timestamp) &&
    typeof v.bin === "string" &&
    Object.hasOwn(ERROR_LABEL, String(v.errorCode)) &&
    ["PASS", "FAIL", "REVIEW"].includes(String(v.status)) &&
    ["NONE", "CULTIVAR_SUSPECT", "QUALITY_SUSPECT", "OTHER"].includes(
      String(v.misclassification),
    ) &&
    ["COMPLETED", "INFERENCING", "TIMEOUT", "ERROR"].includes(
      String(v.processingStatus),
    ) &&
    ["NOT_REQUESTED", "SUCCEEDED", "FALLBACK", "NO_RESPONSE", "REJECTED", "FAILED"].includes(
      String(v.control),
    ) &&
    ["SAVED", "FAILED"].includes(String(v.persistence)) &&
    typeof v.excluded === "boolean" &&
    typeof v.reviewRequired === "boolean" &&
    (v.virtualBrix === null || finite(v.virtualBrix)) &&
    v.brixMeasured === false &&
    (v.imageIndex === null || (finite(v.imageIndex) && Number.isInteger(v.imageIndex))) &&
    (v.inferenceMs === null || finite(v.inferenceMs)) &&
    (v.modelVersion === null || typeof v.modelVersion === "string") &&
    Array.isArray(v.faults) &&
    v.faults.every(validFault) &&
    (v.previewUrl === undefined || validPreview(v.previewUrl))
  );
};
const validFault = (v: unknown) =>
  [
    "INFERENCE_TIMEOUT",
    "INFERENCE_ERROR",
    "DB_ERROR",
    "CONTROL_REJECTED",
    "CONTROL_NO_RESPONSE",
    "CONTROL_FAILED",
  ].includes(String(v));
const validPreview = (v: unknown) =>
  typeof v === "string" && /^\/api\/quality\/previews\/[A-Za-z0-9_-]+$/.test(v);
const validJobPreviews = (v: unknown) =>
  Array.isArray(v) &&
  v.length >= 1 &&
  v.length <= 12 &&
  v.every(
    (frame, index) =>
      object(frame) &&
      frame.index === index &&
      validPreview(frame.previewUrl),
  );
const resultList = (v: unknown, max: number) =>
  Array.isArray(v) && v.length <= max && v.every(validResult);

export function parseSnapshot(value: unknown): QualitySnapshot {
  const v = value;
  if (
    !object(v) ||
    v.contractVersion !== "1" ||
    !["reference", "backend"].includes(String(v.source)) ||
    !finite(v.capturedAt) ||
    !finite(v.revision) ||
    !object(v.state) ||
    !object(v.components) ||
    !object(v.capabilities) ||
    !object(v.retention) ||
    !(v.retention.history === undefined || finite(v.retention.history)) ||
    !finite(v.retention.images) ||
    !counts(v.periodTotals) ||
    !["1", "5", "10", "30"].every((key) =>
      finite((v.periodTotals as Record<string, unknown>)[key]),
    )
  )
    throw new QualityApiError(
      "지원하지 않는 관제 응답입니다. 계약 버전을 확인하세요.",
    );
  const s = v.state;
  if (
    !["running", "dbDown"].every((key) => typeof s[key] === "boolean") ||
    !["throughput"].every((key) =>
      finite(s[key]),
    ) ||
    !["sequence", "tick", "concurrency", "intervalMs"].every(
      (key) => s[key] === undefined || finite(s[key]),
    ) ||
    !(s.scope === undefined || ["ALL", "NEXT"].includes(String(s.scope))) ||
    !Array.isArray(s.faults) ||
    !s.faults.every(validFault) ||
    !object(s.today) ||
    typeof s.today.date !== "string" ||
    ![
      "total",
      "normal",
      "review",
      "excluded",
      "reinspection",
      "inferenceTotalMs",
      "inferenceCount",
    ].every((key) => finite((s.today as Record<string, unknown>)[key])) ||
    !["grades", "varieties", "bins", "suspicions"].every((key) =>
      counts((s.today as Record<string, unknown>)[key]),
    ) ||
    !(s.lastSaved === null || finite(s.lastSaved)) ||
    !resultList(s.history, 200) ||
    !resultList(s.images, 100) ||
    !resultList(s.errors, 50) ||
    !Array.isArray(s.points) ||
    s.points.length > 1800 ||
    !s.points.every(
      (p) =>
        object(p) &&
        ["at", "count", "review", "excluded"].every((key) => finite(p[key])),
    ) ||
    !Array.isArray(s.jobs) ||
    s.jobs.length > 64 ||
    !s.jobs.every(
      (j) =>
        object(j) &&
        typeof j.id === "string" &&
        finite(j.index) &&
        finite(j.started) &&
        finite(j.finish) &&
        Array.isArray(j.faults) &&
        j.faults.every(validFault) &&
        (j.previewUrl === undefined || validPreview(j.previewUrl)) &&
        (j.previews === undefined || validJobPreviews(j.previews)),
    ) ||
    // #88 이전 Backend에는 없다.
    !(
      s.recentCompletedJobs === undefined ||
      (Array.isArray(s.recentCompletedJobs) &&
        s.recentCompletedJobs.length <= 64 &&
        s.recentCompletedJobs.every(
          (j) =>
            object(j) &&
            typeof j.id === "string" &&
            /^[A-Za-z0-9_-]{1,64}$/.test(j.id) &&
            ["COMPLETED", "ERROR", "TIMEOUT"].includes(String(j.status)) &&
            finite(j.completedAt) &&
            finite(j.previewExpiresAt) &&
            validJobPreviews(j.previews),
        ))
    )
  )
    throw new QualityApiError("관제 데이터 형식이 올바르지 않습니다.");
  if (
    !["control", "faults", "review", "deleteImages"].every(
      (key) =>
        typeof (v.capabilities as Record<string, unknown>)[key] === "boolean",
    ) ||
    !Array.isArray(v.capabilities.concurrency) ||
    !v.capabilities.concurrency.every(
      (n) => finite(n) && Number.isInteger(n) && n > 0 && n <= 64,
    ) ||
    !(
      v.capabilities.intervals === undefined ||
      (Array.isArray(v.capabilities.intervals) &&
        v.capabilities.intervals.every(
          (n) => finite(n) && Number.isInteger(n) && n >= 100,
        ))
    ) ||
    !["Simulator", "Inference", "Backend", "MySQL"].every((key) => {
      const c = (v.components as Record<string, unknown>)[key];
      return (
        object(c) &&
        ["healthy", "stopped", "error", "unknown"].includes(String(c.status)) &&
        typeof c.detail === "string" &&
        (c.lastSeenAt === null || finite(c.lastSeenAt))
      );
    })
  )
    throw new QualityApiError(
      "구성요소 상태 또는 제어 권한 응답이 올바르지 않습니다.",
    );
  return v as unknown as QualitySnapshot;
}
export function parseHistory(value: unknown): HistoryPage {
  if (
    !object(value) ||
    !resultList(value.items, 200) ||
    !finite(value.total) ||
    !finite(value.page) ||
    ![50, 100, 200].includes(Number(value.pageSize)) ||
    !finite(value.snapshotAt) ||
    !Array.isArray(value.bins) ||
    !value.bins.every((v) => typeof v === "string")
  )
    throw new QualityApiError("이력 응답 형식이 올바르지 않습니다.");
  return value as unknown as HistoryPage;
}
export function historyQuery(
  filters: QualityFilterState = DEFAULT_QUALITY_FILTERS,
  page = 1,
  snapshotAt?: number,
) {
  const query = new URLSearchParams({
    page: String(page),
    pageSize: String(filters.pageSize),
  });
  for (const [key, value] of Object.entries(filters))
    if (key !== "pageSize" && value && value !== "ALL")
      query.set(key, String(value));
  if (snapshotAt !== undefined) query.set("snapshotAt", String(snapshotAt));
  return query.toString();
}
export async function qualityRequest(path: string, options: RequestInit = {}) {
  let response: Response;
  try {
    response = await fetch(`/api/quality/${path}`, {
      ...options,
      cache: "no-store",
      signal: options.signal ?? AbortSignal.timeout(8000),
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch (error) {
    if (options.signal?.aborted) throw error;
    throw new QualityApiError("서버 응답이 없습니다. 연결 상태를 확인하세요.");
  }
  if (!response.ok)
    throw new QualityApiError(
      response.status === 409
        ? "다른 화면에서 설정이 변경됐습니다. 최신 상태를 확인하고 다시 시도하세요."
        : response.status === 404 || response.status === 410
          ? "이미 만료되었거나 삭제된 항목입니다."
          : response.status === 503
            ? "서비스에 연결할 수 없습니다."
            : `요청을 처리하지 못했습니다 (${response.status}).`,
      response.status,
    );
  return response;
}
export async function getSnapshot(signal?: AbortSignal) {
  return parseSnapshot(
    await (await qualityRequest("snapshot", { signal })).json(),
  );
}
export async function getHistory(
  filters: QualityFilterState,
  page: number,
  snapshotAt?: number,
  signal?: AbortSignal,
) {
  return parseHistory(
    await (
      await qualityRequest(
        `inspections?${historyQuery(filters, page, snapshotAt)}`,
        { signal },
      )
    ).json(),
  );
}
export async function saveReview(
  id: string,
  value: MisclassificationType,
  signal?: AbortSignal,
) {
  await qualityRequest(`inspections/${encodeURIComponent(id)}/review`, {
    method: "PATCH",
    body: JSON.stringify({ misclassification: value }),
    signal,
  });
}
export async function downloadQualityCsv(path: string, name: string) {
  const response = await qualityRequest(path);
  if (!response.headers.get("content-type")?.includes("text/csv"))
    throw new QualityApiError("CSV 응답 형식이 올바르지 않습니다.");
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
