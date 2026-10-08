"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge, Icon, Panel } from "./Dashboard";
import QualityImage from "./QualityImage";
import ThroughputChart from "./ThroughputChart";
import { useDemo } from "./DemoProvider";
import { sampleApples } from "@/lib/sample-apples";
import { formatPercent } from "@/lib/quality-format";
import { qualityBins } from "@/lib/quality-bins";
import {
  FAULTS,
  imageIndexForJob,
  recentThroughput,
  kst,
  periodPoints,
  throughputSeries,
  exceptionOf,
  displayedJobs,
  CONFIDENCE_MIN,
  type Job,
  type Result,
} from "@/lib/quality-runtime";

// 이 화면은 계속 지켜볼 정보만 둔다. 이력·통계·검수 이미지·시연 설정처럼 조작이 많은 기능은 관리자 페이지(/admin)에 있다.
/** 마지막으로 처리한 사과의 판정 요약. 이력에 아직 없으면 반영 중으로 둔다. */
function heldResult(row: Result | undefined) {
  if (!row) return "판정 반영 중";
  const exception = exceptionOf(row);
  if (exception) return `${exception.kind === "error" ? "오류" : "재검사"} · ${exception.reason}`;
  return `${row.variety ?? "—"} ${row.grade ?? "—"}`;
}
// 이 화면은 농장 한 곳의 선별 라인을 관제한다. 배포마다 농장 이름만 바꿔 쓴다.
export const FARM_NAME = process.env.NEXT_PUBLIC_FARM_NAME || "CQC 사과농장";
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
// 선별함 13칸(품종 2 × 등급 3 × 당도 2 + 재검사함)에 오늘 들어간 사과 수를 그린다.
// 칸 색이 진할수록 많이 들어갔고, 방금 처리한 사과가 들어간 칸은 잠깐 테두리가 반짝인다.
const GRADES = ["특", "상", "보통"] as const;
const VARIETIES = ["부사", "양광"] as const;
// 외관은 보통이지만 당도가 높은 칸. 발표의 "못난이 사과" 후보다.
const UGLY_BINS = new Set(["DEMO_BIN_06", "DEMO_BIN_12"]);
function BinMap({
  bins,
  reinspectionRatio,
  recent,
}: {
  bins: Record<string, number>;
  reinspectionRatio: string;
  recent?: { id: string; bin: string };
}) {
  const count = (code: string) => Math.round(bins[code] ?? 0);
  const max = Math.max(1, ...qualityBins.map((bin) => count(bin.code)));
  const review = count("TEST_REINSPECTION_BIN");
  const cell = (code: string, label: string) => {
    const value = count(code);
    const isRecent = recent?.bin === code;
    return (
      <div
        // 같은 칸에 연달아 들어와도 반짝임이 다시 시작되도록 최근 검사 ID를 key에 넣는다.
        key={isRecent ? `${code}-${recent?.id}` : code}
        className={`qc-bin${UGLY_BINS.has(code) ? " ugly" : ""}${isRecent ? " recent" : ""}`}
        style={{ "--fill": `${Math.round((value / max) * 100)}%` } as React.CSSProperties}
        title={`${code} · ${label} · ${value.toLocaleString("ko-KR")}건`}
      >
        <span>{code.slice(-2)}{UGLY_BINS.has(code) && " ★"}</span>
        <strong>{value}</strong>
      </div>
    );
  };
  return (
    <div className="qc-binmap" aria-label="오늘 선별함별 사과 수">
      <span className="qc-bin-corner" />
      {GRADES.map((grade) => (
        <span key={grade} className="qc-bin-grade">{grade}</span>
      ))}
      <span className="qc-bin-corner" />
      {GRADES.flatMap((grade) =>
        ["14° 미만", "14° 이상"].map((band) => (
          <span key={`${grade}-${band}`} className="qc-bin-band">{band === "14° 미만" ? "<14" : "≥14"}</span>
        )),
      )}
      {VARIETIES.map((variety) => {
        const row = qualityBins.filter((bin) => bin.variety === variety);
        const total = row.reduce((sum, bin) => sum + count(bin.code), 0);
        return [
          <span key={variety} className="qc-bin-variety">
            {variety}
            <small>{total.toLocaleString("ko-KR")}</small>
          </span>,
          ...row.map((bin) => cell(bin.code, `${bin.variety} ${bin.grade} 당도 ${bin.sweetness}`)),
        ];
      })}
      <div
        key={recent?.bin === "TEST_REINSPECTION_BIN" ? `review-${recent.id}` : "review"}
        className={`qc-bin qc-bin-review${Number(reinspectionRatio) > REINSPECTION_ALERT ? " alert" : ""}${recent?.bin === "TEST_REINSPECTION_BIN" ? " recent" : ""}`}
        title={`TEST_REINSPECTION_BIN · ${review.toLocaleString("ko-KR")}건`}
      >
        <span>재검사함</span>
        <strong>{review.toLocaleString("ko-KR")}</strong>
        <small>재검사율<br />{reinspectionRatio}%</small>
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
  const { state, snapshot, error, connectedAt, stale } = demo.connection;
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
  const activeFaults = [
    ...new Set([...state.faults, ...state.jobs.flatMap((job) => job.faults)]),
  ];
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
          <Link href="/admin" className="qc-admin-link">품질 관리 →</Link>
          <Link href="/market" className="qc-market-link">입찰 시장 →</Link>
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
                <div className="qc-bin-head">
                  <strong>오늘 선별함</strong>
                  <small>선별 명령 성공 기준 · ★ 못난이 사과 후보</small>
                </div>
                <BinMap
                  bins={state.today.bins ?? {}}
                  reinspectionRatio={reinspectionRatio}
                  recent={state.history[0] && { id: state.history[0].id, bin: state.history[0].bin }}
                />
                {(!remote || snapshot?.source === "reference") && (
                  <p className="qc-muted">참조 시연 수치이며 실제 모델 성능이 아닙니다.</p>
                )}
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
    </main>
  );
}
