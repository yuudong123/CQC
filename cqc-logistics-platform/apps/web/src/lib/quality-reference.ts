import {
  DEFAULT_QUALITY_FILTERS,
  MISCLASSIFICATION_LABEL,
  ERROR_LABEL,
  PROCESSING_STATUS_LABEL,
  type QualityFilterState,
  type MisclassificationType,
} from "./quality-contract";
import {
  initialRuntime,
  step,
  classifyResult,
  periodPoints,
  csvCell,
  kst,
  FAULTS,
  type Runtime,
} from "./quality-runtime";
import { summarizeInspections } from "./quality-statistics";
import { DemoFaultImageStore } from "./quality-fault-images";
import type { QualitySnapshot } from "./quality-api";

/** HTTP contract reference only: no MySQL, inference or physical control. */
export class QualityReferenceService {
  state: Runtime = initialRuntime();
  revision = 0;
  readonly faultImages = new DemoFaultImageStore();
  constructor(
    private readonly now = Date.now,
    private readonly image?: (index: number, view?: number) => Promise<Uint8Array>,
  ) {}
  tick() {
    const before = this.state.faults.join();
    const previous = this.state;
    this.state = step(this.state, this.now());
    this.faultImages.advance(previous, this.state);
    if (before !== this.state.faults.join()) this.revision++;
  }
  snapshot(): QualitySnapshot {
    const now = this.now();
    const preview = (id: string) =>
      `/api/quality/previews/${encodeURIComponent(id)}`;
    const state = {
      ...this.state,
      history: this.state.history.slice(0, 200),
      points: this.state.points.slice(-30),
      jobs: this.state.jobs.map((row) => ({
        ...row,
        previewUrl: preview(row.id),
      })),
      images: this.state.images.map((row) => ({
        ...row,
        previewUrl: preview(row.id),
      })),
    };
    return {
      contractVersion: "1",
      source: "reference",
      capturedAt: now,
      revision: this.revision,
      capabilities: {
        control: true,
        faults: true,
        review: true,
        deleteImages: true,
        concurrency: [1, 2, 4],
      },
      retention: { history: 2000, images: this.faultImages.items.length },
      periodTotals: Object.fromEntries(
        [1, 5, 10, 30].map((n) => [
          String(n),
          periodPoints(
            this.state.points,
            n,
            this.state.dbDown ? (this.state.points.at(-1)?.at ?? now) : now,
          ).reduce((sum, p) => sum + p.count, 0),
        ]),
      ) as QualitySnapshot["periodTotals"],
      components: {
        Simulator: {
          status: state.running ? "healthy" : "stopped",
          lastSeenAt: now,
          detail: state.running ? "참조 입력 중" : "입력 정지",
        },
        Inference: {
          status: state.faults.some((f) => f.startsWith("INFERENCE"))
            ? "error"
            : "unknown",
          lastSeenAt: null,
          detail: "참조 응답 · 모델 미연결",
        },
        Backend: {
          status: "healthy",
          lastSeenAt: now,
          detail: "참조 API 응답",
        },
        MySQL: {
          status: state.dbDown ? "error" : "unknown",
          lastSeenAt: null,
          detail: state.dbDown ? "저장 실패 시연" : "메모리 저장 · DB 미연결",
        },
      },
      state,
    };
  }
  private json(data: unknown, status = 200) {
    return Response.json(data, {
      status,
      headers: { "Cache-Control": "no-store", "X-CQC-Contract": "1" },
    });
  }
  private fail(status: number, code: string) {
    return this.json({ code }, status);
  }
  private csv(rows: unknown[][]) {
    return new Response(
      "\uFEFF" + rows.map((row) => row.map(csvCell).join(",")).join("\r\n"),
      {
        headers: {
          "Content-Type": "text/csv; charset=utf-8",
          "Cache-Control": "no-store",
          "Content-Disposition": 'attachment; filename="cqc-reference.csv"',
        },
      },
    );
  }
  private query(url: URL) {
    const q = url.searchParams;
    const allowed = new Set([
      ...Object.keys(DEFAULT_QUALITY_FILTERS),
      "page",
      "snapshotAt",
    ]);
    if ([...q.keys()].some((key) => !allowed.has(key)))
      throw new Error("UNKNOWN_FILTER");
    const f = {
      ...DEFAULT_QUALITY_FILTERS,
      ...Object.fromEntries(q),
    } as unknown as QualityFilterState;
    for (const value of [f.from, f.to])
      if (
        value &&
        (!/^\d{4}-\d{2}-\d{2}$/.test(value) ||
          Number.isNaN(Date.parse(value)) ||
          new Date(value).toISOString().slice(0, 10) !== value)
      )
        throw new Error("INVALID_DATE");
    if (f.from && f.to && f.from > f.to) throw new Error("INVALID_RANGE");
    if (
      !["ALL", "부사", "양광"].includes(f.variety) ||
      !["ALL", "특", "상", "보통"].includes(f.grade) ||
      !["ALL", ...Object.keys(PROCESSING_STATUS_LABEL)].includes(
        f.processingStatus,
      ) ||
      !["ALL", ...Object.keys(ERROR_LABEL)].includes(f.errorCode) ||
      !["ALL", ...Object.keys(MISCLASSIFICATION_LABEL)].includes(
        f.misclassification,
      )
    )
      throw new Error("INVALID_FILTER");
    const page = Number(q.get("page") ?? 1),
      pageSize = Number(q.get("pageSize") ?? 50),
      snapshotAt = Number(q.get("snapshotAt") ?? this.now());
    if (
      !Number.isInteger(page) ||
      page < 1 ||
      ![50, 100, 200].includes(pageSize) ||
      !Number.isFinite(snapshotAt) ||
      snapshotAt < 0 ||
      snapshotAt > this.now()
    )
      throw new Error("INVALID_PAGE");
    const items = this.state.history.filter(
      (row) =>
        row.timestamp <= snapshotAt &&
        (!f.from || row.date >= f.from) &&
        (!f.to || row.date <= f.to) &&
        (f.variety === "ALL" || (!row.excluded && row.variety === f.variety)) &&
        (f.grade === "ALL" || (!row.excluded && row.grade === f.grade)) &&
        (f.bin === "ALL" || row.bin === f.bin) &&
        (f.processingStatus === "ALL" ||
          row.processingStatus === f.processingStatus) &&
        (f.errorCode === "ALL" ||
          (f.errorCode === "NONE"
            ? !row.faults.length
            : row.faults.includes(f.errorCode))) &&
        (f.misclassification === "ALL" ||
          row.misclassification === f.misclassification),
    );
    return { items, page, pageSize, snapshotAt };
  }
  async handle(request: Request): Promise<Response> {
    const url = new URL(request.url),
      path = url.pathname.replace(/^\/v1\/quality\/?/, ""),
      method = request.method;
    if (url.pathname === "/health" && method === "GET")
      return this.json({ status: "ok", source: "reference" });
    if (!url.pathname.startsWith("/v1/quality/"))
      return this.fail(404, "NOT_FOUND");
    try {
      if (path === "snapshot" && method === "GET")
        return this.json(this.snapshot());
      if (
        ["inspections", "inspections.csv"].includes(path) &&
        method === "GET"
      ) {
        if (this.state.dbDown) return this.fail(503, "DB_UNAVAILABLE");
        const q = this.query(url);
        if (path.endsWith(".csv"))
          return this.csv([
            [
              "inspection_id",
              "date",
              "time_kst",
              "variety",
              "grade",
              "cultivar_confidence_pct",
              "quality_confidence_pct",
              "inference_ms",
              "model_version",
              "target_bin",
              "processing_status",
              "control_status",
              "persistence_status",
              "error_codes",
              "misclassification",
              "virtual_brix",
              "brix_is_measured",
            ],
            ...q.items.map((r) => [
              r.id,
              r.date,
              r.time,
              r.excluded ? "" : r.variety,
              r.excluded ? "" : r.grade,
              r.cultivarConfidence,
              r.excluded ? "" : r.confidence,
              r.inferenceMs,
              r.modelVersion,
              r.bin,
              r.processingStatus,
              r.control,
              r.persistence,
              r.faults.join("|"),
              r.misclassification,
              r.virtualBrix,
              false,
            ]),
          ]);
        return this.json({
          ...q,
          total: q.items.length,
          items: q.items.slice((q.page - 1) * q.pageSize, q.page * q.pageSize),
          bins: [...new Set(this.state.history.map((r) => r.bin))],
        });
      }
      if (
        (path === "statistics" ||
          (path === "statistics.csv" &&
            (url.searchParams.has("from") || url.searchParams.has("to")))) &&
        method === "GET"
      ) {
        if (this.state.dbDown) return this.fail(503, "DB_UNAVAILABLE");
        const q = this.query(url),
          summary = summarizeInspections(q.items);
        if (path === "statistics") return this.json(summary);
        const rows: unknown[][] = [
          ["mode", "from_kst", "to_kst", "group", "key", "value"],
        ];
        for (const [key, value] of Object.entries(summary))
          if (typeof value === "number")
            rows.push([
              "REFERENCE",
              url.searchParams.get("from"),
              url.searchParams.get("to"),
              "total",
              key,
              value,
            ]);
          else
            for (const [name, count] of Object.entries(value))
              rows.push([
                "REFERENCE",
                url.searchParams.get("from"),
                url.searchParams.get("to"),
                key,
                name,
                count,
              ]);
        rows.push([
          "REFERENCE",
          url.searchParams.get("from"),
          url.searchParams.get("to"),
          "total",
          "reinspection_ratio",
          summary.total ? summary.reinspection / summary.total : 0,
        ]);
        rows.push([
          "REFERENCE",
          url.searchParams.get("from"),
          url.searchParams.get("to"),
          "total",
          "average_inference_ms",
          summary.inferenceCount
            ? summary.inferenceTotalMs / summary.inferenceCount
            : "",
        ]);
        return this.csv(rows);
      }
      if (path === "statistics.csv" && method === "GET") {
        const minutes = Number(url.searchParams.get("minutes") ?? 1);
        if (![1, 5, 10, 30].includes(minutes))
          return this.fail(422, "INVALID_PERIOD");
        const t = this.state.today,
          average = t.inferenceCount
            ? t.inferenceTotalMs / t.inferenceCount
            : null;
        const rows: unknown[][] = [
          ["mode", "date_kst", "section", "key", "value", "last_saved_at"],
        ];
        const add = (section: string, key: string, value: unknown) =>
          rows.push([
            "REFERENCE",
            t.date,
            section,
            key,
            value,
            this.state.lastSaved
              ? kst(this.state.lastSaved).replace("Z", "+09:00")
              : "",
          ]);
        for (const [key, value] of Object.entries({
          total: t.total,
          normal: t.normal,
          excluded: t.excluded,
          reinspection: t.reinspection,
          reinspection_ratio: t.total ? t.reinspection / t.total : 0,
          average_inference_ms: average,
        }))
          add("today", key, value);
        for (const group of [
          "grades",
          "varieties",
          "bins",
          "suspicions",
        ] as const)
          for (const [key, value] of Object.entries(t[group]))
            add(group, key, value);
        for (const p of periodPoints(
          this.state.points,
          minutes,
          this.state.points.at(-1)?.at ?? this.now(),
        ))
          add(
            `last_${minutes}_minutes`,
            kst(p.at).replace("Z", "+09:00"),
            p.count,
          );
        return this.csv(rows);
      }
      if (path === "simulator" && method === "PUT") {
        const body = await request.json();
        if (
          !body ||
          typeof body !== "object" ||
          Array.isArray(body) ||
          Object.keys(body).some(
            (k) =>
              ![
                "expectedRevision",
                "running",
                "concurrency",
                "scope",
                "faults",
              ].includes(k),
          )
        )
          return this.fail(422, "INVALID_SETTINGS");
        if (body.expectedRevision !== this.revision)
          return this.fail(409, "REVISION_CONFLICT");
        if (
          (body.running !== undefined && typeof body.running !== "boolean") ||
          (body.concurrency !== undefined &&
            ![1, 2, 4].includes(body.concurrency)) ||
          (body.scope !== undefined && !["ALL", "NEXT"].includes(body.scope)) ||
          (body.faults !== undefined &&
            (!Array.isArray(body.faults) ||
              body.faults.length > 5 ||
              new Set(body.faults).size !== body.faults.length ||
              body.faults.some((f: string) => !Object.hasOwn(FAULTS, f))))
        )
          return this.fail(422, "INVALID_SETTINGS");
        const { expectedRevision: _, ...changes } = body;
        void _;
        this.state = { ...this.state, ...changes };
        this.revision++;
        return this.json(this.snapshot());
      }
      const review = path.match(/^inspections\/([A-Za-z0-9_-]+)\/review$/);
      if (review && method === "PATCH") {
        if (this.state.dbDown) return this.fail(503, "DB_UNAVAILABLE");
        const body = await request.json();
        if (
          !body ||
          !Object.hasOwn(MISCLASSIFICATION_LABEL, body.misclassification) ||
          Object.keys(body).some((k) => k !== "misclassification")
        )
          return this.fail(422, "INVALID_REVIEW");
        if (!this.state.history.some((r) => r.id === review[1]))
          return this.fail(404, "INSPECTION_EXPIRED");
        this.state = classifyResult(
          this.state,
          review[1],
          body.misclassification as MisclassificationType,
        );
        return this.json({
          inspectionId: review[1],
          misclassification: body.misclassification,
        });
      }
      if (path === "fault-images" && method === "GET")
        return this.json({ items: this.faultImages.items });
      if (path === "fault-images" && method === "DELETE") {
        const body = await request.json();
        if (
          !body ||
          !Array.isArray(body.ids) ||
          body.ids.length > 100 ||
          body.ids.some((id: unknown) => typeof id !== "string") ||
          Object.keys(body).some((k) => k !== "ids")
        )
          return this.fail(422, "INVALID_IDS");
        const deletedIds = this.faultImages.remove(body.ids);
        return this.json({ deletedIds });
      }
      const preview = path.match(/^previews\/([A-Za-z0-9_-]+)$/);
      if (preview && method === "GET") {
        const item = this.faultImages.items.find((r) => r.id === preview[1]),
          job = this.state.jobs.find((r) => r.id === preview[1]);
        if (!item && !job) return this.fail(410, "IMAGE_EXPIRED");
        if (!this.image) return this.fail(503, "IMAGE_UNAVAILABLE");
        const source = item ? this.faultImages.source(item.id) : undefined;
        const match = source?.match(/apple-(\d+)-(\d+)/);
        const bytes = await this.image(match ? Number(match[1]) : job!.index % 6, item?.imageIndex ?? 0);
        return new Response(bytes as BodyInit, {
          headers: {
            "Content-Type": "image/webp",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
          },
        });
      }
      return this.fail(404, "NOT_FOUND");
    } catch {
      return this.fail(422, "INVALID_REQUEST");
    }
  }
}
