"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Badge, Panel, Stats } from "./Dashboard";
import QualityHistory from "./QualityHistory";
import QualityStatistics from "./QualityStatistics";
import ThroughputChart from "./ThroughputChart";
import { useDemo } from "./DemoProvider";
import type { FaultImage } from "@/lib/quality-fault-images";
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
  CONFIDENCE_MIN,
  type Fault,
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
  const [confirmation, setConfirmation] = useState<string[] | null>(null);
  const [error, setError] = useState("");
  const entries = images.map(image => {
    const record = state.images.find(row => row.id === image.inspectionId) ?? state.history.find(row => row.id === image.inspectionId);
    return { ...image, misclassification: record?.misclassification ?? "NONE", hasRecord: !!record };
  });
  const rows = entries.filter(
    (row) => category === "ALL" || row.misclassification === category,
  );
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
          {rows.length}장 표시 · 실제 보존 {retained} / 100장
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
          ? "서버에 보관된 장애 이미지입니다."
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
              alt={`${preview.id} 장애 이미지`}
            />
          </div>
          <div>
            <h3>{preview.id}</h3>
            <p>{preview.inspectionId} · view {preview.imageIndex} · {preview.errorCode}</p>
            <button onClick={() => setSelected(null)}>미리보기 닫기</button>
          </div>
        </div>
      )}
      <table>
        <thead>
          <tr>
            <th>검사 ID</th>
            <th>발생 시각</th>
            <th>장애</th>
            <th>오판 의심</th>
            <th>이미지</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{row.inspectionId}<br /><small>view {row.imageIndex} · {row.id}</small></td>
              <td>{kst(row.createdAt).slice(11, 19)}</td>
              <td>{row.errorCode}</td>
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
        <p className="qc-empty">보관된 장애 이미지가 없습니다.</p>
      )}
    </>
  );
}
// 서버 검사 ID(UUID)만 앞 8자리로 줄이고 시연 ID는 그대로 둔다.
const shortId = (id: string) => (id.length > 12 ? id.slice(0, 8) : id);
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
  return (
    <main className="qc-console">
      <section className="qc-top">
        <h1>품질 검사 관제</h1>
        <span className="qc-line">{remote ? "현재 연결 설비 · 선별 라인 1" : "시연 농가 · 선별 라인 1"}</span>
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
            장애 이미지 {remote ? (snapshot?.retention.images ?? 0) : faultImages.length}장
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
      <Stats
        items={[
          {
            label: "오늘 저장 검사",
            value: `${state.today.total}건`,
            icon: "document",
          },
          {
            label: "오늘 재검사율",
            value: (
              <>
                {reinspectionRatio}%<small> {state.today.reinspection}건</small>
              </>
            ),
            icon: "alert",
            tone: "warning",
          },
          {
            label:
              !remote || snapshot?.source === "reference"
                ? "평균 추론 · 예시"
                : "평균 추론",
            value: averageInference,
            icon: "check",
          },
          {
            label: "현재 처리량",
            value: `${recentThroughput(state.points).toFixed(1)}건/초`,
            icon: "clock",
          },
          {
            label: "통계 제외",
            value: `${state.today.excluded}건`,
            icon: "alert",
            tone: "danger",
          },
        ]}
      />
      <div className="qc-body">
        <div className="qc-col">
          <Panel
            title={remote ? "처리 중 사과" : "사과 그룹 · 12장 동시 촬영"}
            className="qc-jobs-panel"
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
              {state.jobs.map((job) => (
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
                    <strong title={job.id}>{job.id}</strong>
                    {!remote && <small>그룹 {sampleApples[imageIndexForJob(job.index)].group}</small>}
                    <span>{remote ? "추론 처리 중" : "12장 입력 · 판정 시연"}</span>
                    <small>
                      {job.faults.length
                        ? job.faults.map((code) => FAULTS[code]).join(" · ")
                        : remote && snapshot?.source === "backend"
                          ? "처리 중"
                          : "정상 시연"}
                    </small>
                  </div>
                </article>
              ))}
              {!state.jobs.length && (
                <p className="qc-empty">처리 중인 사과가 없습니다.</p>
              )}
            </div>
          </Panel>
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
                    <th>검사 ID</th>
                    <th>목적지</th>
                  </tr>
                </thead>
                <tbody>
                  {shownExceptions.slice(0, 50).map(({ row, kind, reason, lowCultivar, lowQuality }) => (
                    <tr key={row.id}>
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
                      <td title={row.id}>{shortId(row.id)}</td>
                      <td>{row.bin}</td>
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
          <Panel title="시스템 상태" className="qc-status-panel" icon="box" action={<small>1초 갱신</small>}>
            <div className="qc-scroll">
              <div className="qc-components">
                {(remote && snapshot
                  ? Object.entries(snapshot.components).map(
                      ([name, component]) => [
                        name,
                        component.detail || component.status,
                      ],
                    )
                  : [
                      [
                        "Simulator",
                        state.running ? "예시 입력 중" : "예시 입력 정지",
                      ],
                      [
                        "Inference",
                        activeFaults.some((code) => code.startsWith("INFERENCE"))
                          ? "장애 시연"
                          : "예시 응답",
                      ],
                      ["Backend", health],
                      ["MySQL", state.dbDown ? "저장 실패 시연" : "미연결"],
                    ]
                ).map(([name, status]) => (
                  <div key={name}>
                    <strong>{name}</strong>
                    <Badge
                      tone={
                        status.includes("실패") || status.includes("장애")
                          ? "danger"
                          : "neutral"
                      }
                    >
                      {status}
                    </Badge>
                    {remote &&
                      snapshot?.components[
                        name as keyof typeof snapshot.components
                      ].lastSeenAt && (
                        <small>
                          수신{" "}
                          {kst(
                            snapshot.components[
                              name as keyof typeof snapshot.components
                            ].lastSeenAt!,
                          ).slice(11, 19)}
                        </small>
                      )}
                  </div>
                ))}
              </div>
              <h3>설비·연동 오류</h3>
              <p className="qc-muted">
                추론·제어·저장 결과 기준 · 사과별 재검사는 아래 목록
              </p>
              {state.errors.slice(0, 8).map((row) => (
                <div className="qc-error" key={row.id}>
                  <strong>{row.id}</strong>
                  <time>{row.time}</time>
                  <p>{row.faults.map((code) => FAULTS[code]).join(" · ")}</p>
                  <small>
                    제어:{" "}
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
                    · 저장: {row.persistence === "SAVED" ? "완료" : "실패"}
                  </small>
                </div>
              ))}
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
                  ? "장애 이미지 관리"
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
