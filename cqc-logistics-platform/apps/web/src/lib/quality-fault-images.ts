import type { Runtime } from "./quality-runtime";
import { exceptionOf } from "./quality-runtime";
import { validInspectionId } from "./quality-api";
import { sampleApples } from "./sample-apples";
export type FaultErrorCode =
  "INFERENCE_TIMEOUT" | "INFERENCE_ERROR" | "INFERENCE_CONNECTION_ERROR" | "INFERENCE_HTTP_ERROR" | "INFERENCE_INVALID_RESPONSE";
export type ImageCategory = "SYSTEM_ERROR" | "LOW_CONFIDENCE";
/** 검수 이미지(#55). category 이하 필드는 #90 이전 Backend에는 없어서 선택으로 받는다. */
export type FaultImage = {
  id: string; inspectionId: string; imageIndex: number; createdAt: number;
  errorCode: FaultErrorCode | null;
  previewUrl: string;
  category?: ImageCategory;
  decisionReason?: string;
  cultivarConfidence?: number | null;
  qualityConfidence?: number | null;
  appliedCultivarThreshold?: number | null;
  appliedQualityThreshold?: number | null;
};
const ERROR_CODES = ["INFERENCE_TIMEOUT", "INFERENCE_ERROR", "INFERENCE_CONNECTION_ERROR", "INFERENCE_HTTP_ERROR", "INFERENCE_INVALID_RESPONSE"];
/** 보존 한도: 시스템 오류 100장, 저신뢰 재검사 200장(#55). */
export const IMAGE_LIMIT: Record<ImageCategory, number> = { SYSTEM_ERROR: 100, LOW_CONFIDENCE: 200 };
const ratio = (v: unknown) => v === undefined || v === null || (typeof v === "number" && Number.isFinite(v) && v >= 0 && v <= 1);
export function parseFaultImages(value: unknown): FaultImage[] {
  const v = value as { items?: FaultImage[] } | null;
  if (!v || !Array.isArray(v.items) || v.items.length > IMAGE_LIMIT.SYSTEM_ERROR + IMAGE_LIMIT.LOW_CONFIDENCE || v.items.some(r =>
    !r || typeof r.id !== "string" || !/^[A-Za-z0-9_-]{1,64}$/.test(r.id) ||
    !validInspectionId(r.inspectionId) ||
    !Number.isInteger(r.imageIndex) || r.imageIndex < 0 || r.imageIndex > 11 ||
    !Number.isFinite(r.createdAt) || r.createdAt < 0 ||
    !(r.errorCode === null ? r.category === "LOW_CONFIDENCE" : ERROR_CODES.includes(r.errorCode)) ||
    !(r.category === undefined || r.category === "SYSTEM_ERROR" || r.category === "LOW_CONFIDENCE") ||
    !(r.decisionReason === undefined || typeof r.decisionReason === "string") ||
    ![r.cultivarConfidence, r.qualityConfidence, r.appliedCultivarThreshold, r.appliedQualityThreshold].every(ratio) ||
    r.previewUrl !== `/api/quality/previews/${r.id}`
  ) || new Set(v.items.map(r => r.id)).size !== v.items.length)
    throw new Error("검수 이미지 응답이 올바르지 않습니다.");
  return v.items;
}
export const imageCategory = (r: FaultImage): ImageCategory => r.category ?? "SYSTEM_ERROR";
export const CATEGORY_LABEL: Record<ImageCategory, string> = { SYSTEM_ERROR: "시스템 오류", LOW_CONFIDENCE: "저신뢰 재검사" };
const REASON_LABEL: Record<string, string> = {
  LOW_CULTIVAR_CONFIDENCE: "품종 신뢰도 미달",
  LOW_QUALITY_CONFIDENCE: "품질 신뢰도 미달",
  LOW_BOTH_CONFIDENCE: "품종·품질 신뢰도 미달",
  INFERENCE_TIMEOUT: "추론 시간 초과",
  INFERENCE_DEADLINE_EXCEEDED: "추론 시간 초과",
  INFERENCE_ERROR: "추론 오류",
  INFERENCE_CONNECTION_ERROR: "추론 연결 실패",
  INFERENCE_HTTP_ERROR: "추론 응답 오류",
  INFERENCE_INVALID_RESPONSE: "추론 응답 형식 오류",
};
/** 사람이 읽는 사유. Backend 사유 코드가 없으면 오류 코드로 대신한다. */
export function imageReason(r: FaultImage): string {
  const code = r.decisionReason ?? r.errorCode ?? "";
  return REASON_LABEL[code] ?? (code || "사유 없음");
}
const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
/** 기준에 못 미친 신뢰도만 "품질 55.8% < 60.0%"처럼 보여준다. */
export function imageEvidence(r: FaultImage): string {
  const parts: string[] = [];
  for (const [label, value, limit] of [
    ["품종", r.cultivarConfidence, r.appliedCultivarThreshold],
    ["품질", r.qualityConfidence, r.appliedQualityThreshold],
  ] as const) {
    if (typeof value === "number" && typeof limit === "number" && value < limit) parts.push(`${label} ${pct(value)} < ${pct(limit)}`);
  }
  return parts.join(" · ");
}
/** Separate image retention from inspection history; only newly completed jobs add files. */
export class DemoFaultImageStore {
  items: FaultImage[] = [];
  private sources = new Map<string, string>();
  advance(before: Runtime, after: Runtime) {
    const finished = (rows: Runtime["history"]) => rows.filter(r => before.jobs.some(j => j.id === r.id));
    const completed = [...finished(after.images), ...finished(after.history)].filter((r, i, all) => all.findIndex(o => o.id === r.id) === i);
    const added: FaultImage[] = [];
    for (const row of completed) {
      const errorCode = row.faults.find(f => f === "INFERENCE_TIMEOUT" || f === "INFERENCE_ERROR") ?? null;
      const exception = exceptionOf(row);
      const low = !errorCode && exception?.kind === "reinspection" && (exception.lowCultivar || exception.lowQuality);
      if ((!errorCode && !low) || row.imageIndex === null) continue;
      const decisionReason = errorCode ?? (exception!.lowCultivar && exception!.lowQuality ? "LOW_BOTH_CONFIDENCE" : exception!.lowCultivar ? "LOW_CULTIVAR_CONFIDENCE" : "LOW_QUALITY_CONFIDENCE");
      const share = (v: number | null) => (v === null ? null : v / 100);
      sampleApples[row.imageIndex]?.images.forEach((src, imageIndex) => {
        const id = `${row.id}_view_${imageIndex}`;
        this.sources.set(id, src);
        added.push({ id, inspectionId: row.id, imageIndex, createdAt: row.timestamp,
          errorCode, previewUrl: `/api/quality/previews/${id}`,
          category: errorCode ? "SYSTEM_ERROR" : "LOW_CONFIDENCE", decisionReason,
          cultivarConfidence: share(row.cultivarConfidence), qualityConfidence: share(row.confidence),
          appliedCultivarThreshold: 0.5, appliedQualityThreshold: 0.6 });
      });
    }
    const merged = [...added, ...this.items];
    this.items = (["SYSTEM_ERROR", "LOW_CONFIDENCE"] as const).flatMap(c => merged.filter(r => imageCategory(r) === c).slice(0, IMAGE_LIMIT[c]))
      .sort((x, y) => y.createdAt - x.createdAt);
    this.prune();
  }
  remove(ids: string[]) {
    const deletedIds = this.items.filter(r => ids.includes(r.id)).map(r => r.id);
    this.items = this.items.filter(r => !ids.includes(r.id)); this.prune();
    return deletedIds;
  }
  source(id: string) { return this.sources.get(id); }
  private prune() {
    const kept = new Set(this.items.map(r => r.id));
    for (const id of this.sources.keys()) if (!kept.has(id)) this.sources.delete(id);
  }
}
export type QualityPoll<S> = { snapshot: S; images: FaultImage[] | null; imageError: string };
/**
 * Loads the control snapshot and the fault image inventory in parallel.
 * A snapshot failure is fatal for the poll; an image inventory failure (e.g. Backend
 * storage not configured → 503 IMAGE_UNAVAILABLE) keeps the snapshot and reports
 * the image error separately so the control screen does not freeze.
 */
export async function loadQualityPoll<S>(
  loadSnapshot: () => Promise<S>,
  loadImages: () => Promise<FaultImage[]>,
): Promise<QualityPoll<S>> {
  const [snapshot, images] = await Promise.allSettled([loadSnapshot(), loadImages()]);
  if (snapshot.status === "rejected") throw snapshot.reason;
  if (images.status === "fulfilled") return { snapshot: snapshot.value, images: images.value, imageError: "" };
  const reason = images.reason instanceof Error ? images.reason.message : "";
  return {
    snapshot: snapshot.value,
    images: null,
    imageError: `검수 이미지 목록을 불러오지 못했습니다${reason ? `: ${reason}` : "."} 관제 상태는 계속 갱신됩니다.`,
  };
}
