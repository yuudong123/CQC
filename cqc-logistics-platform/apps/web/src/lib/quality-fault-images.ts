import type { Runtime } from "./quality-runtime";
import { sampleApples } from "./sample-apples";
export type FaultImage = {
  id: string; inspectionId: string; imageIndex: number; createdAt: number;
  errorCode: "INFERENCE_TIMEOUT" | "INFERENCE_ERROR" | "INFERENCE_CONNECTION_ERROR" | "INFERENCE_HTTP_ERROR" | "INFERENCE_INVALID_RESPONSE";
  previewUrl: string;
};
export function parseFaultImages(value: unknown): FaultImage[] {
  const v = value as { items?: FaultImage[] } | null;
  if (!v || !Array.isArray(v.items) || v.items.length > 100 || v.items.some(r =>
    !r || typeof r.id !== "string" || !/^[A-Za-z0-9_-]{1,64}$/.test(r.id) ||
    typeof r.inspectionId !== "string" || !/^[A-Za-z0-9_-]{1,64}$/.test(r.inspectionId) ||
    !Number.isInteger(r.imageIndex) || r.imageIndex < 0 || r.imageIndex > 11 ||
    !Number.isFinite(r.createdAt) || r.createdAt < 0 ||
    !["INFERENCE_TIMEOUT", "INFERENCE_ERROR", "INFERENCE_CONNECTION_ERROR", "INFERENCE_HTTP_ERROR", "INFERENCE_INVALID_RESPONSE"].includes(r.errorCode) ||
    r.previewUrl !== `/api/quality/previews/${r.id}`
  ) || new Set(v.items.map(r => r.id)).size !== v.items.length)
    throw new Error("장애 이미지 응답이 올바르지 않습니다.");
  return v.items;
}
/** Separate image retention from inspection history; only newly completed jobs add files. */
export class DemoFaultImageStore {
  items: FaultImage[] = [];
  private sources = new Map<string, string>();
  advance(before: Runtime, after: Runtime) {
    const completed = after.images.filter(r => before.jobs.some(j => j.id === r.id));
    const added: FaultImage[] = [];
    for (const row of completed) {
      const errorCode = row.faults.find(f => f === "INFERENCE_TIMEOUT" || f === "INFERENCE_ERROR");
      if (!errorCode || row.imageIndex === null) continue;
      sampleApples[row.imageIndex]?.images.forEach((src, imageIndex) => {
        const id = `${row.id}_view_${imageIndex}`;
        this.sources.set(id, src);
        added.push({ id, inspectionId: row.id, imageIndex, createdAt: row.timestamp,
          errorCode, previewUrl: `/api/quality/previews/${id}` });
      });
    }
    this.items = [...added, ...this.items].slice(0, 100);
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
    imageError: `장애 이미지 목록을 불러오지 못했습니다${reason ? `: ${reason}` : "."} 관제 상태는 계속 갱신됩니다.`,
  };
}
