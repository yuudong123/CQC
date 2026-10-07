"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Badge, Icon, Panel } from "./Dashboard";
import QualityHistory from "./QualityHistory";
import QualityStatistics from "./QualityStatistics";
import ThroughputChart from "./ThroughputChart";
import { useDemo } from "./DemoProvider";
import {
  CATEGORY_LABEL,
  IMAGE_LIMIT,
  imageCategory,
  imageEvidence,
  imageReason,
  type FaultImage,
  type ImageCategory,
} from "@/lib/quality-fault-images";
import { downloadQualityCsv } from "@/lib/quality-api";
import { sampleApples } from "@/lib/sample-apples";
import { formatPercent } from "@/lib/quality-format";
import {
  MISCLASSIFICATION_LABEL,
  type MisclassificationType,
} from "@/lib/quality-contract";
import {
  FAULTS,
  imageIndexForJob,
  LINE_INTERVALS,
  recentThroughput,
  csvCell,
  kst,
  periodPoints,
  throughputSeries,
  exceptionOf,
  displayedJobs,
  CONFIDENCE_MIN,
  type Fault,
  type Job,
  type Result,
  type Runtime,
} from "@/lib/quality-runtime";

type Tab = "history" | "images" | "faults" | "statistics" | null;
function QualityImage({
  src,
  alt,
  remote,
}: {
  src?: string;
  alt: string;
  remote: boolean;
}) {
  const [failed, setFailed] = useState(false);
  return !src || failed ? (
    <p className="qc-muted">이미지 조회 불가 · 만료 또는 연결 끊김</p>
  ) : (
    <Image
      src={src}
      alt={alt}
      fill
      sizes="(max-width:650px) 40vw, 500px"
      loading="eager"
      unoptimized={remote}
      onError={() => setFailed(true)}
    />
  );
}
/** 마지막으로 처리한 사과의 판정 요약. 이력에 아직 없으면 반영 중으로 둔다. */
function heldResult(row: Result | undefined) {
  if (!row) return "판정 반영 중";
  const exception = exceptionOf(row);
  if (exception) return `${exception.kind === "error" ? "오류" : "재검사"} · ${exception.reason}`;
  return `${row.variety ?? "—"} ${row.grade ?? "—"}`;
}
function Modal({
  title,
  close,
  children,
}: {
  title: string;
  close: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    const previous = document.activeElement as HTMLElement | null;
    dialog?.showModal();
    return () => {
      dialog?.close();
      previous?.focus();
    };
  }, []);
  return (
    <dialog ref={ref} className="qc-dialog" onCancel={close} aria-label={title}>
      <div className="qc-dialog-heading">
        <h2>{title}</h2>
        <button onClick={close} autoFocus>
          닫기
        </button>
      </div>
      <div className="qc-dialog-body">{children}</div>
    </dialog>
  );
}
function FaultImages({
  state,
  images,
  imageSource,
  retained,
  loadError,
  classify,
  removeImages,
  remote,
  pending,
  allowReview,
  allowDelete,
}: {
  state: Runtime;
  images: FaultImage[];
  imageSource: (id: string) => string | undefined;
  retained: number;
  loadError: string;
  classify: (id: string, value: MisclassificationType) => Promise<void>;
  removeImages: (ids: string[]) => Promise<void>;
  remote: boolean;
  pending: boolean;
  allowReview: boolean;
  allowDelete: boolean;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [category, setCategory] = useState("ALL");
  const [kind, setKind] = useState<"ALL" | ImageCategory>("ALL");
  const [confirmation, setConfirmation] = useState<string[] | null>(null);
  const [error, setError] = useState("");
  const entries = images.map(image => {
    const record = state.images.find(row => row.id === image.inspectionId) ?? state.history.find(row => row.id === image.inspectionId);
    return { ...image, misclassification: record?.misclassification ?? "NONE", hasRecord: !!record };
  });
  const rows = entries.filter(
    (row) =>
      (kind === "ALL" || imageCategory(row) === kind) &&
      (category === "ALL" || row.misclassification === category),
  );
  const kept = (c: ImageCategory) => images.filter((row) => imageCategory(row) === c).length;
  const preview = entries.find((row) => row.id === selected);
  async function remove() {
    if (!confirmation) return;
    try {
      await removeImages(confirmation);
      if (selected && confirmation.includes(selected)) setSelected(null);
      setConfirmation(null);
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "삭제 실패");
    }
  }
  return (
    <>
      <div className="qc-actions">
        <label>
          구분{" "}
          <select
            value={kind}
            onChange={(event) => setKind(event.target.value as "ALL" | ImageCategory)}
          >
            <option value="ALL">전체</option>
            {Object.entries(CATEGORY_LABEL).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          오판 의심 필터{" "}
          <select
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          >
            <option value="ALL">전체</option>
            {Object.entries(MISCLASSIFICATION_LABEL).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <span>
          {rows.length}장 표시 · 보존 {retained}장 (시스템 오류 {kept("SYSTEM_ERROR")}/{IMAGE_LIMIT.SYSTEM_ERROR} · 저신뢰 {kept("LOW_CONFIDENCE")}/{IMAGE_LIMIT.LOW_CONFIDENCE})
        </span>
        <button
          disabled={!images.length || pending || !allowDelete}
          onClick={() => setConfirmation(images.map((row) => row.id))}
        >
          전체 이미지 삭제
        </button>
      </div>
      <p className="qc-muted">
        {remote
          ? "서버에 보관된 검수 이미지입니다. 시스템 오류와 저신뢰 재검사 사과를 사유와 함께 보관합니다."
          : "예시 이미지 관리 · 삭제는 이 브라우저의 목록에만 적용됩니다."}{" "}
        검사 이력은 유지됩니다.
      </p>
      {loadError && (
        <p role="alert" className="qc-warning">
          {loadError}
        </p>
      )}
      {error && (
        <p role="alert" className="qc-warning">
          {error}
        </p>
      )}
      {confirmation && (
        <div className="qc-warning" role="alert">
          <span>
            선택한 이미지 {confirmation.length}장을 삭제할까요? 확인 이후 새로
            들어온 이미지는 유지됩니다.
          </span>
          <button disabled={pending} onClick={remove}>
            삭제 확인
          </button>
          <button disabled={pending} onClick={() => setConfirmation(null)}>
            취소
          </button>
        </div>
      )}
      {preview && (
        <div className="qc-preview">
          <div className="qc-preview-image">
            <QualityImage
              key={preview.id}
              remote={remote}
              src={
                remote ? preview.previewUrl : imageSource(preview.id)
              }
              alt={`${preview.id} 검수 이미지`}
            />
          </div>
          <div>
            <h3>{preview.id}</h3>
            <p>{preview.inspectionId} · view {preview.imageIndex} · {CATEGORY_LABEL[imageCategory(preview)]} · {imageReason(preview)}</p>
            {imageEvidence(preview) && <p>{imageEvidence(preview)}</p>}
            <button onClick={() => setSelected(null)}>미리보기 닫기</button>
          </div>
        </div>
      )}
      <table>
        <thead>
          <tr>
            <th>검사 ID</th>
            <th>발생 시각</th>
            <th>구분</th>
            <th>사유</th>
            <th>오판 의심</th>
            <th>이미지</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{row.inspectionId}<br /><small>view {row.imageIndex} · {row.id}</small></td>
              <td>{kst(row.createdAt).slice(11, 19)}</td>
              <td>{CATEGORY_LABEL[imageCategory(row)]}</td>
              <td>
                {imageReason(row)}
                {imageEvidence(row) && <><br /><small>{imageEvidence(row)}</small></>}
              </td>
              <td>
                <select
                  aria-label={`${row.id} 오판 의심`}
                  value={row.misclassification}
                  disabled={pending || !allowReview || !row.hasRecord}
                  onChange={(event) =>
                    void classify(
                      row.inspectionId,
                      event.target.value as MisclassificationType,
                    ).catch((cause) => setError(cause.message))
                  }
                >
                  {Object.entries(MISCLASSIFICATION_LABEL).map(
                    ([key, label]) => (
                      <option key={key} value={key}>
                        {label}
                      </option>
                    ),
                  )}
                </select>
              </td>
              <td>
                <button onClick={() => setSelected(row.id)}>미리보기</button>
                <button
                  disabled={pending || !allowDelete}
                  onClick={() => setConfirmation([row.id])}
                >
                  삭제
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && (
        <p className="qc-empty">보관된 검수 이미지가 없습니다.</p>
      )}
    </>
  );
}
// 이 화면은 농장 한 곳의 선별 라인을 관제한다. 배포마다 농장 이름만 바꿔 쓴다.
const FARM_NAME = process.env.NEXT_PUBLIC_FARM_NAME || "CQC 사과농장";
// 오늘 재검사율이 이 값(%)을 넘으면 빨갛게 표시한다(수용시험 기준 20% 이하).
const REINSPECTION_ALERT = 20;
// 선별함 코드를 사람이 읽는 이름으로 바꾼다(코드는 툴팁·이력·CSV에 남는다).
const binLabel = (code: string) =>
  code === "TEST_REINSPECTION_BIN"
    ? "재검사함"
    : /^DEMO_BIN_(\d+)$/.test(code)
      ? `선별함 ${code.slice(-2)}`
      : code;
// 구성요소 상태 → 색. 정상은 초록, 정지·확인 중은 주황, 오류는 빨강.
function componentTone(status: string, text: string) {
  if (status === "error" || /실패|장애|끊김|오류|불가/.test(text)) return "danger";
  if (status === "healthy" || /정상|응답|입력 중|전송 중|준비 완료|조회 성공/.test(text)) return "success";
  return "warning";
}
const percent = (value: number, total: number) =>
  total ? ((value / total) * 100).toFixed(1) : "0.0";
function RatioBar({
  label,
  values,
  total,
}: {
  label: string;
  values: Record<string, number>;
  total: number;
}) {
  const entries = Object.entries(values);
  return (
    <div className="qc-ratio">
      <strong>{label}</strong>
      <div
        className="qc-ratio-bar"
        role="img"
        aria-label={`${label} ${entries.map(([key, value]) => `${key} ${percent(value, total)}%`).join(", ")}`}
      >
        {entries.map(
          ([key, value], index) =>
            value > 0 && (
              <span
                key={key}
                data-index={index}
                style={{ flexGrow: value }}
                title={`${key} ${value}건`}
              />
            ),
        )}
      </div>
      <div className="qc-ratio-legend">
        {entries.map(([key, value], index) => (
          <span key={key} data-index={index}>
            {key} {value}건 ({percent(value, total)}%)
          </span>
        ))}
      </div>
    </div>
  );
}
export default function QualityConsole({
  mode = "demo",
}: {
  mode?: "demo" | "api";
}) {
  const remote = mode === "api";
  const demo = useDemo();
  const {
    state,
    snapshot,
    error,
    pending,
    connectedAt,
    stale,
    configure,
    classify,
    removeImages,
    faultImages,
    faultImageError,
    faultImageSource,
  } = demo.connection;
  const [actionError, setActionError] = useState("");
  const action = (operation: Promise<void>) => {
    setActionError("");
    void operation.catch((cause) =>
      setActionError(cause instanceof Error ? cause.message : "요청 실패"),
    );
  };
  const disabled = pending || (remote && (stale || !snapshot));
  const allowControl =
    !remote || (!!snapshot?.capabilities.control && state.concurrency !== undefined);
  const intervalOptions = remote
    ? (snapshot?.capabilities.intervals ?? [])
    : LINE_INTERVALS;
  const allowSpeed =
    !remote || (intervalOptions.length > 0 && state.intervalMs !== undefined);
  const allowFaults =
    !remote || (!!snapshot?.capabilities.faults && state.scope !== undefined);
  const [tab, setTab] = useState<Tab>(null);
  const [exceptionKind, setExceptionKind] = useState<
    "all" | "reinspection" | "error"
  >("all");
  const [minutes, setMinutes] = useState(1);
  const [health, setHealth] = useState("확인 중");
  useEffect(() => {
    if (remote) return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    let controller: AbortController;
    async function poll() {
      controller = new AbortController();
      try {
        const response = await fetch("/api/quality/health", {
          cache: "no-store",
          signal: controller.signal,
        });
        const data = await response.json();
        if (!disposed)
          setHealth(
            response.ok && data.status === "ok"
              ? "응답 정상"
              : data.status === "unconfigured"
                ? "연결 미설정"
                : "연결 끊김",
          );
      } catch {
        if (!disposed) setHealth("연결 끊김");
      } finally {
        if (!disposed) timer = setTimeout(poll, 1000);
      }
    }
    void poll();
    return () => {
      disposed = true;
      clearTimeout(timer);
      controller?.abort();
    };
  }, [remote]);
  // 처리가 끝난 사과도 다음 사과가 올 때까지 남겨 패널 높이를 고정한다.
  // 같은 key로 계속 그려서 이미 받은 미리보기를 다시 요청하지 않는다(완료 후 서버 미리보기는 만료됨).
  // 처리 중일 때 못 잡은 사과는 recentCompletedJobs(완료 후 약 3초)로 이어서 보여준다.
  const [lastJobs, setLastJobs] = useState<Job[]>([]);
  const shown = displayedJobs(state.jobs, lastJobs, state.recentCompletedJobs);
  const jobKey = (jobs: Job[]) => jobs.map((job) => `${job.id}:${job.previews?.length ?? 0}`).join();
  if (shown.jobs.length && jobKey(shown.jobs) !== jobKey(lastJobs)) setLastJobs(shown.jobs);
  const lastPoint = state.points.at(-1);
  const trendEnd = Math.max(
    snapshot?.capturedAt ?? 0,
    lastPoint?.at ?? 0,
    state.history[0]?.timestamp ?? 0,
  );
  // 서버 이력은 최근 200건, 브라우저 예시는 2,000건까지 들고 있다.
  const trend = throughputSeries(
    state.history,
    trendEnd,
    5,
    20,
    2,
    remote ? 200 : 2000,
  );
  // 정상 통과는 처리 중 사과 패널과 검사 이력에서 보고, 여기는 다시 볼 사과만 남긴다.
  const exceptions = state.history.flatMap((row) => {
    const exception = exceptionOf(row);
    return exception ? [{ row, ...exception }] : [];
  });
  const exceptionCount = {
    all: exceptions.length,
    reinspection: exceptions.filter((item) => item.kind === "reinspection").length,
    error: exceptions.filter((item) => item.kind === "error").length,
  };
  const shownExceptions = exceptions.filter(
    (item) => exceptionKind === "all" || item.kind === exceptionKind,
  );
  const reinspectionRatio = percent(state.today.reinspection, state.today.total);
  const averageInference = state.today.inferenceCount
    ? `${(state.today.inferenceTotalMs / state.today.inferenceCount).toFixed(1)}ms`
    : "—";
  const period = periodPoints(state.points, minutes, lastPoint?.at ?? 0);
  const count = remote
    ? (snapshot?.periodTotals[String(minutes) as "1" | "5" | "10" | "30"] ?? 0)
    : period.reduce((sum, point) => sum + point.count, 0);
  function exportStats() {
    if (remote) {
      action(
        downloadQualityCsv(
          `statistics.csv?minutes=${minutes}`,
          "cqc-statistics.csv",
        ),
      );
      return;
    }
    const rows: unknown[][] = [
      ["mode", "date_kst", "section", "key", "value", "last_saved_at"],
    ];
    const add = (section: string, key: string, value: number) =>
      rows.push([
        "DEMO",
        state.today.date,
        section,
        key,
        value,
        state.lastSaved ? kst(state.lastSaved).replace("Z", "+09:00") : "",
      ]);
    add("today", "total", state.today.total);
    add("today", "excluded", state.today.excluded);
    add("today", "reinspection", state.today.reinspection);
    add(
      "today",
      "reinspection_ratio",
      state.today.total ? state.today.reinspection / state.today.total : 0,
    );
    add(
      "today",
      "average_inference_ms",
      state.today.inferenceCount
        ? state.today.inferenceTotalMs / state.today.inferenceCount
        : 0,
    );
    for (const [key, value] of Object.entries(state.today.suspicions))
      add("suspicions", key, value);
    for (const [key, value] of Object.entries(state.today.grades))
      add("grade", key, value);
    for (const [key, value] of Object.entries(state.today.varieties))
      add("variety", key, value);
    for (const [key, value] of Object.entries(state.today.bins))
      add("successful_bin", key, value);
    for (const point of period)
      add(`last_${minutes}_minutes`, kst(point.at).slice(11, 23), point.count);
    const url = URL.createObjectURL(
      new Blob(
        ["\uFEFF" + rows.map((row) => row.map(csvCell).join(",")).join("\r\n")],
        { type: "text/csv;charset=utf-8" },
      ),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "cqc-demo-statistics.csv";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
  const activeFaults = [
    ...new Set([...state.faults, ...state.jobs.flatMap((job) => job.faults)]),
  ];
  const toggle = (fault: Fault) =>
    action(
      configure({
        faults: state.faults.includes(fault)
          ? state.faults.filter((item) => item !== fault)
          : [...state.faults, fault],
      }),
    );
  const components: [string, string, string][] =
    remote && snapshot
      ? Object.entries(snapshot.components).map(([name, component]) => [
          name,
          component.status,
          component.detail || component.status,
        ])
      : [
          ["Simulator", "", state.running ? "예시 입력 중" : "예시 입력 정지"],
          [
            "Inference",
            "",
            activeFaults.some((code) => code.startsWith("INFERENCE")) ? "장애 시연" : "예시 응답",
          ],
          ["Backend", "", health],
          ["MySQL", "", state.dbDown ? "저장 실패 시연" : "미연결"],
        ];
  const tones = components.map(([, status, text]) => componentTone(status, text));
  const problems = tones.filter((tone) => tone !== "success").length;
  const overall = tones.includes("danger") ? "danger" : problems ? "warning" : "success";
  const lastSeen = (name: string) => {
    const seen = remote && snapshot?.components[name as keyof typeof snapshot.components]?.lastSeenAt;
    return seen ? `수신 ${kst(seen).slice(11, 19)}` : "";
  };
  const errorRow = (row: Result) => (
    <div className="qc-error" key={row.id} title={`검사 ID ${row.id}`}>
      <time>{row.time.slice(0, 8)}</time>
      <p>{row.faults.map((code) => FAULTS[code]).join(" · ")}</p>
      <small>
        제어{" "}
        {row.control === "NO_RESPONSE"
          ? "전송 실패"
          : row.control === "NOT_REQUESTED"
            ? "미요청"
            : row.control === "FALLBACK"
              ? "재검사 대체 1회"
              : row.control === "REJECTED"
                ? "거부"
                : row.control === "FAILED"
                  ? "실패"
                  : "성공"}{" "}
        · 저장 {row.persistence === "SAVED" ? "완료" : "실패"}
      </small>
    </div>
  );
  return (
    <main className="qc-console">
      <section className="qc-top">
        <h1>{FARM_NAME} 품질 관제</h1>
        <span className="qc-line">{remote ? "우리 농장 전용 · 선별 라인 1" : "시연 농가 · 선별 라인 1"}</span>
        <Badge
          tone={
            remote && snapshot?.source === "backend" ? "success" : "warning"
          }
        >
          {!remote
            ? "브라우저 예시"
            : !snapshot
              ? "서버 연결 중"
              : snapshot.source === "reference"
                ? "참조 API · 모델/DB 미연결"
                : "서버 관제"}
        </Badge>
        <div className="qc-actions">
          <Link href="/market" className="qc-market-link">입찰 시장 →</Link>
          <button disabled={demo.count >= 3} onClick={demo.toggle}>{demo.enabled ? "자동 경매 정지" : demo.count >= 3 ? "자동 경매 완료" : "자동 경매 시연"}</button>
          <button onClick={() => setTab("history")}>검사 이력</button>
          <button onClick={() => setTab("statistics")}>기간 통계</button>
          <button onClick={() => setTab("images")}>
            검수 이미지 {remote ? (snapshot?.retention.images ?? 0) : faultImages.length}장
          </button>
          <button onClick={() => setTab("faults")}>시연 설정</button>
          <button
            className="qc-run"
            disabled={disabled || !allowControl}
            onClick={() => action(configure({ running: !state.running }))}
          >
            {state.running ? "입력 정지" : "입력 재개"}
          </button>
        </div>
      </section>
      <div className="qc-notices" aria-live="polite">
        {demo.error && <div className="qc-warning">자동 경매: {demo.error} · 입찰 시장에서 확인하세요.</div>}
        {remote && stale && (
          <div className="qc-warning">
            {error || "서버 상태 확인 중"} ·{" "}
            {connectedAt
              ? `마지막 수신 ${kst(connectedAt).slice(11, 19)} · 기존 화면 유지`
              : "수신 전 · 표시 수치는 집계 결과가 아닙니다."}
          </div>
        )}
        {actionError && (
          <div className="qc-warning" role="alert">
            {actionError}
            <button onClick={() => setActionError("")}>닫기</button>
          </div>
        )}
        {activeFaults.length > 0 && (
          <div className="qc-warning">
            장애 시연 중 ·{" "}
            {activeFaults.map((code) => FAULTS[code]).join(" / ")} ·{" "}
            {state.scope === "NEXT"
              ? "다음 1건 (접수 후 해제)"
              : state.scope === "ALL"
                ? "전체 신규 요청"
                : "적용 범위 미제공"}
          </div>
        )}
        {state.dbDown && (
          <div className="qc-warning">
            DB 저장 실패 · 선별은 계속 진행됩니다. 통계는 마지막 저장 시점{" "}
            {state.lastSaved ? kst(state.lastSaved).slice(11, 23) : "없음"}{" "}
            기준이며 실패 이력은 복구하지 않습니다.
          </div>
        )}
        {!state.running && (
          <div className="qc-warning">
            입력 정지 · 진행 중 {state.jobs.length}건은 완료 후 종료
            {state.sequence !== undefined && ` · 다음 순번 ${state.sequence + 1}`}
          </div>
        )}
      </div>
      {/* 멀리서도 보이도록 오늘 저장 검사와 재검사율을 크게 둔다. 나머지 지표는 오른쪽에 작게 모은다. */}
      <section className="stats qc-kpis" aria-label="운영 요약">
        <article className="stat hero">
          <span className="stat-icon"><Icon name="document" /></span>
          <div>
            <p>오늘 저장 검사</p>
            <strong>{state.today.total.toLocaleString("ko-KR")}건</strong>
          </div>
        </article>
        <article className={`stat hero warning ${Number(reinspectionRatio) > REINSPECTION_ALERT ? "alert" : ""}`}>
          <span className="stat-icon"><Icon name="alert" /></span>
          <div>
            <p>오늘 재검사율</p>
            <strong>
              {reinspectionRatio}%<small> {state.today.reinspection.toLocaleString("ko-KR")}건</small>
            </strong>
          </div>
        </article>
        <article className="stat qc-kpi-mini">
          <dl>
            <div>
              <dt>{!remote || snapshot?.source === "reference" ? "평균 추론 · 예시" : "평균 추론"}</dt>
              <dd>{averageInference}</dd>
            </div>
            <div>
              <dt>현재 처리량</dt>
              <dd>{recentThroughput(state.points).toFixed(1)}건/초</dd>
            </div>
            <div className="danger">
              <dt>통계 제외</dt>
              <dd>{state.today.excluded}건</dd>
            </div>
          </dl>
        </article>
      </section>
      <div className="qc-body">
        <div className="qc-col">
          <Panel
            title="재검사·오류 사과"
            className="qc-exception-panel"
            icon="alert"
            action={
              <div className="qc-segment" role="group" aria-label="재검사·오류 구분">
                {(
                  [
                    ["all", "전체"],
                    ["reinspection", "재검사"],
                    ["error", "오류"],
                  ] as const
                ).map(([key, label]) => (
                  <button
                    key={key}
                    aria-pressed={exceptionKind === key}
                    onClick={() => setExceptionKind(key)}
                  >
                    {label} {exceptionCount[key]}
                  </button>
                ))}
              </div>
            }
          >
            <div className="qc-scroll">
              <p className="qc-muted qc-exception-note">
                최근 판정 {state.history.length}건 중 · 신뢰도 기준 품종{" "}
                {CONFIDENCE_MIN.cultivar}% / 품질 {CONFIDENCE_MIN.quality}% 미만은
                재검사 · 전체 기간은 검사 이력
              </p>
              <table>
                <thead>
                  <tr>
                    <th>시각</th>
                    <th>구분</th>
                    <th>사유</th>
                    <th>품종 / 등급</th>
                    <th>품종 / 품질 신뢰도</th>
                    <th>목적지</th>
                  </tr>
                </thead>
                <tbody>
                  {shownExceptions.slice(0, 50).map(({ row, kind, reason, lowCultivar, lowQuality }) => (
                    <tr key={row.id} title={`검사 ID ${row.id}`}>
                      <td>{row.time}</td>
                      <td>
                        <Badge tone={kind === "error" ? "danger" : "warning"}>
                          {kind === "error" ? "오류" : "재검사"}
                        </Badge>
                      </td>
                      <td>{reason}</td>
                      <td>
                        {row.excluded ? "—" : `${row.variety} / ${row.grade}`}
                      </td>
                      <td>
                        {row.excluded ? (
                          "—"
                        ) : (
                          <>
                            <span className={lowCultivar ? "qc-low" : undefined}>
                              {formatPercent(row.cultivarConfidence)}
                            </span>
                            {" / "}
                            <span className={lowQuality ? "qc-low" : undefined}>
                              {formatPercent(row.confidence)}
                            </span>
                          </>
                        )}
                      </td>
                      <td title={row.bin}>{binLabel(row.bin)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!shownExceptions.length && (
                <p className="qc-empty">
                  {state.history.length
                    ? `최근 판정 ${state.history.length}건 중 ${exceptionKind === "error" ? "오류" : exceptionKind === "reinspection" ? "재검사" : "재검사·오류"} 없음`
                    : "저장된 판정이 없습니다."}
                </p>
              )}
            </div>
          </Panel>
        </div>
        <div className="qc-col">
          <Panel
            title="시스템 상태"
            className="qc-status-panel"
            icon="box"
            action={
              <Badge tone={overall}>
                {problems ? `확인 필요 ${problems}` : "모두 정상"}
              </Badge>
            }
          >
            <div className="qc-scroll">
              <div className="qc-components">
                {components.map(([name, status, text]) => (
                  <div key={name} className={`qc-component ${componentTone(status, text)}`} title={lastSeen(name)}>
                    <i aria-hidden="true" />
                    <strong>{name}</strong>
                    <span>{text}</span>
                  </div>
                ))}
              </div>
              <div className="qc-error-head">
                <h3>설비·연동 오류</h3>
                <small>추론·제어·저장 결과 기준</small>
              </div>
              {state.errors.slice(0, 3).map((row) => errorRow(row))}
              {state.errors.length > 3 && (
                <details className="qc-error-more">
                  <summary>이전 오류 {Math.min(state.errors.length, 8) - 3}건 더 보기</summary>
                  {state.errors.slice(3, 8).map((row) => errorRow(row))}
                </details>
              )}
              {!state.errors.length && <p className="qc-muted">설비·연동 오류 없음</p>}
            </div>
          </Panel>
          <Panel
            title="처리 현황"
            className="qc-trend-panel"
            icon="market"
            action={
              <label>
                기간{" "}
                <select
                  aria-label="통계 기간"
                  value={minutes}
                  onChange={(event) => setMinutes(Number(event.target.value))}
                >
                  {[1, 5, 10, 30].map((value) => (
                    <option key={value} value={value}>
                      {value}분
                    </option>
                  ))}
                </select>
              </label>
            }
          >
            <div className="qc-scroll qc-trend-body">
              <div className="qc-trend-main">
                <div className="qc-period">
                  <strong>{count}건</strong>
                  <span>최근 {minutes}분 저장 · 수집된 구간 기준</span>
                </div>
                <ThroughputChart
                  series={trend}
                  end={trendEnd}
                  minutes={5}
                  target={state.intervalMs ? 1000 / state.intervalMs : null}
                  events={exceptions.map(({ row, kind, reason }) => ({
                    at: row.timestamp,
                    kind,
                    reason,
                  }))}
                />
                <div className="qc-chart-label">
                  <span>최근 5분 · 20초 이동평균 · 점은 재검사·오류 시점</span>
                </div>
              </div>
              <div className="qc-trend-side">
                <p>
                  오늘 품종·품질 집계 대상 {state.today.normal}건 · 시간 초과·추론
                  오류 제외
                </p>
                <div className="qc-distributions">
                  <RatioBar
                    label="등급"
                    values={state.today.grades ?? {}}
                    total={state.today.normal}
                  />
                  <RatioBar
                    label="품종"
                    values={state.today.varieties ?? {}}
                    total={state.today.normal}
                  />
                  <div className="qc-trend-foot">
                    <span>
                      오늘 재검사 {state.today.reinspection}건 · {reinspectionRatio}% ·
                      오판 의심{" "}
                      {Object.values(state.today.suspicions).reduce(
                        (sum, value) => sum + value,
                        0,
                      )}
                      건
                    </span>
                    <details>
                      <summary>선별 목적지별 성공 명령</summary>
                      {Object.entries(state.today.bins ?? {}).map(([key, value]) => (
                        <p key={key}>
                          {key} · {value}건
                        </p>
                      ))}
                    </details>
                    <button onClick={exportStats}>통계 CSV</button>
                  </div>
                </div>
                <p className="qc-muted">
                  {!remote || snapshot?.source === "reference"
                    ? "참조 시연 수치이며 실제 모델 성능이 아닙니다."
                    : "서버 저장 결과 기준 · 시간 초과와 추론 오류는 품종·품질 집계에서 제외"}
                </p>
              </div>
            </div>
          </Panel>
          <Panel
            title={remote ? "처리 중 사과" : "사과 그룹 · 12장 동시 촬영"}
            className="qc-jobs-panel qc-jobs-compact"
            icon="camera"
            action={
              <Badge tone={state.running ? "success" : "warning"}>
                {state.running ? "입력 중" : "정지"}
                {state.intervalMs !== undefined && ` · ${state.intervalMs / 1000}초 간격`}
                {remote && state.concurrency !== undefined && (
                  <> · {state.concurrency === 1 ? "순차" : `${state.concurrency}개 병렬`}</>
                )}
              </Badge>
            }
          >
            <div className="qc-scroll qc-jobs">
              {shown.jobs.map((job) => (
                <article key={job.id} className="qc-job">
                  {remote && job.previews?.length ? (
                    <div className="qc-frame-area"><div className="qc-frame-grid" aria-label={`${job.id} 처리 중 이미지 ${job.previews.length}장`}>
                      {job.previews.map((frame) => (
                        <div className="qc-live-frame" key={frame.index}>
                          <QualityImage
                            remote
                            src={frame.previewUrl}
                            alt={`${job.id} 프레임 ${frame.index + 1}`}
                          />
                          <span>{String(frame.index + 1).padStart(2, "0")}</span>
                        </div>
                      ))}
                    </div></div>
                  ) : remote && <div className="qc-job-image">
                    <QualityImage
                      key={job.id}
                      remote={remote}
                      src={
                        remote
                          ? job.previewUrl
                          : sampleApples[imageIndexForJob(job.index)]
                              .images[0]
                      }
                      alt={`${job.id} 처리 중 이미지`}
                    />
                  </div>}
                  {!remote && <div className="qc-frame-area"><div className="qc-frame-grid" aria-label={`${job.id} 동일 사과 12장`}>
                    {sampleApples[imageIndexForJob(job.index)].images.map((src, frame) => <div key={src}>
                      <Image src={src} alt={`${job.id} 프레임 ${frame + 1}`} width={120} height={120} unoptimized />
                      <span>{String(frame + 1).padStart(2, "0")}</span>
                    </div>)}
                  </div></div>}
                  <div className="qc-job-info">
                    <strong title={`검사 ID ${job.id}`}>{kst(job.started).slice(11, 19)} 투입</strong>
                    {!remote && <small>그룹 {sampleApples[imageIndexForJob(job.index)].group}</small>}
                    <span>
                      {shown.held
                        ? "처리 완료 · 다음 사과 대기"
                        : remote
                          ? "추론 처리 중"
                          : "12장 입력 · 판정 시연"}
                    </span>
                    <small>
                      {shown.held
                        ? heldResult(state.history.find((row) => row.id === job.id))
                        : job.faults.length
                          ? job.faults.map((code) => FAULTS[code]).join(" · ")
                          : remote && snapshot?.source === "backend"
                            ? "처리 중"
                            : "정상 시연"}
                    </small>
                  </div>
                </article>
              ))}
              {!shown.jobs.length && (
                // 첫 사과가 오기 전에도 12칸 자리를 잡아 패널 높이가 바뀌지 않게 한다.
                <article className="qc-job">
                  <div className="qc-frame-area"><div className="qc-frame-grid" aria-hidden="true">
                    {Array.from({ length: 12 }, (_, frame) => <div key={frame} />)}
                  </div></div>
                  <div className="qc-job-info">
                    <span>처리 중인 사과가 없습니다.</span>
                  </div>
                </article>
              )}
            </div>
          </Panel>
        </div>
      </div>
      {tab && (
        <Modal
          title={
            tab === "statistics"
              ? "기간 통계 분석"
              : tab === "history"
                ? "검사 이력 관리"
                : tab === "images"
                  ? "검수 이미지 관리"
                  : "시연 설정"
          }
          close={() => setTab(null)}
        >
          {actionError && <p role="alert" className="qc-warning">{actionError}</p>}
          {tab === "statistics" && (
            <QualityStatistics
              remote={remote}
              records={state.history}
              reference={!remote || snapshot?.source === "reference"}
            />
          )}
          {tab === "history" && (
            <QualityHistory
              records={state.history}
              remote={remote}
              allowReview={!remote || !!snapshot?.capabilities.review}
              classify={classify}
            />
          )}
          {tab === "images" && (
            <FaultImages
              images={faultImages}
              imageSource={faultImageSource}
              retained={remote ? (snapshot?.retention.images ?? 0) : faultImages.length}
              loadError={faultImageError}
              state={state}
              remote={remote}
              pending={disabled}
              allowReview={!remote || !!snapshot?.capabilities.review}
              allowDelete={!remote || !!snapshot?.capabilities.deleteImages}
              classify={classify}
              removeImages={removeImages}
            />
          )}
          {tab === "faults" && (
            <>
              <p>
                {remote
                  ? "서버가 허용한 설정만 조작할 수 있습니다. 응답 성공 후 적용됩니다."
                  : "브라우저 예시 시연입니다. 새로고침하면 설정이 초기화됩니다."}
              </p>
              <div className="qc-actions">
                <label>
                  라인 속도{" "}
                  <select
                    aria-label="라인 속도"
                    value={state.intervalMs ?? ""}
                    disabled={disabled || !allowSpeed}
                    onChange={(event) =>
                      action(
                        configure({ intervalMs: Number(event.target.value) }),
                      )
                    }
                  >
                    {!allowSpeed && <option value="">제공 안 됨</option>}
                    {intervalOptions.map((value) => (
                      <option key={value} value={value}>
                        {value / 1000}초마다 1묶음
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  처리 방식{" "}
                  <select
                    aria-label="동시 처리 수"
                    value={state.concurrency ?? ""}
                    disabled={disabled || !allowControl}
                    onChange={(event) =>
                      action(
                        configure({ concurrency: Number(event.target.value) }),
                      )
                    }
                  >
                    {(remote
                      ? (snapshot?.capabilities.concurrency ?? [])
                      : [1, 2, 4]
                    ).map((value) => (
                      <option key={value} value={value}>
                        {value === 1 ? "순차 1개" : `병렬 ${value}개`}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  적용 범위{" "}
                  <select
                    aria-label="장애 적용 범위"
                    value={state.scope ?? ""}
                    disabled={disabled || !allowFaults}
                    onChange={(event) =>
                      action(
                        configure({
                          scope: event.target.value as Runtime["scope"],
                        }),
                      )
                    }
                  >
                    <option value="ALL">전체 신규 요청</option>
                    <option value="NEXT">다음 1건</option>
                  </select>
                </label>
              </div>
              <div className="qc-faults">
                {Object.entries(FAULTS).map(([code, label]) => (
                  <label key={code}>
                    <input
                      type="checkbox"
                      checked={state.faults.includes(code as Fault)}
                      disabled={disabled || !allowFaults}
                      onChange={() => toggle(code as Fault)}
                    />
                    {label}
                  </label>
                ))}
              </div>
              <button
                disabled={disabled || !allowFaults}
                onClick={() => action(configure({ faults: [] }))}
              >
                장애 토글 모두 해제
              </button>
              <p className="qc-muted">
                진행 중인 요청은 접수 당시 설정으로 완료됩니다. 실제 서비스의
                동시 처리 수는 서버가 제공한 허용 목록을 따릅니다. 라인 속도는
                사과 묶음 투입을 시작하는 간격이며, 한 건 처리가 더 오래 걸리면
                끝나는 대로 다음 묶음을 넣습니다.
              </p>
            </>
          )}
        </Modal>
      )}
    </main>
  );
}
