"use client";

import Link from "next/link";
import { useState } from "react";
import { Badge } from "./Dashboard";
import QualityHistory from "./QualityHistory";
import QualityImage from "./QualityImage";
import QualityStatistics from "./QualityStatistics";
import { FARM_NAME } from "./QualityConsole";
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
import {
  MISCLASSIFICATION_LABEL,
  type MisclassificationType,
} from "@/lib/quality-contract";
import {
  FAULTS,
  LINE_INTERVALS,
  csvCell,
  kst,
  periodPoints,
  type Fault,
  type Runtime,
} from "@/lib/quality-runtime";

// 관제 화면은 지켜보기만 하고, 마우스 조작이 많은 관리 기능은 이 페이지 탭으로 모은다.
type Tab = "history" | "statistics" | "images" | "settings";
const TABS: [Tab, string][] = [
  ["history", "검사 이력"],
  ["statistics", "기간 통계"],
  ["images", "검수 이미지"],
  ["settings", "시연 설정"],
];
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


export default function QualityAdmin({
  mode = "demo",
}: {
  mode?: "demo" | "api";
}) {
  const remote = mode === "api";
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
  } = useDemo().connection;
  const [tab, setTab] = useState<Tab>("history");
  const [minutes, setMinutes] = useState(1);
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
  const imageCount = remote ? (snapshot?.retention.images ?? 0) : faultImages.length;
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
  // 오늘 집계와 최근 N분 처리량을 CSV로 받는다(관제 화면에 있던 "통계 CSV"를 옮겨 왔다).
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
    const period = periodPoints(state.points, minutes, state.points.at(-1)?.at ?? 0);
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
        ["﻿" + rows.map((row) => row.map(csvCell).join(",")).join("\r\n")],
        { type: "text/csv;charset=utf-8" },
      ),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "cqc-demo-statistics.csv";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
  return (
    <main className="qc-admin">
      <section className="qc-top">
        <h1>{FARM_NAME} 품질 관리</h1>
        <span className="qc-line">관리자 · 선별 라인 1</span>
        <Badge tone={remote && snapshot?.source === "backend" ? "success" : "warning"}>
          {!remote
            ? "브라우저 예시"
            : !snapshot
              ? "서버 연결 중"
              : snapshot.source === "reference"
                ? "참조 API · 모델/DB 미연결"
                : "서버 연결"}
        </Badge>
        <div className="qc-actions">
          <Link href="/" className="qc-market-link">← 관제 화면</Link>
        </div>
      </section>
      <div className="qc-notices" aria-live="polite">
        {remote && stale && (
          <div className="qc-warning">
            {error || "서버 상태 확인 중"} ·{" "}
            {connectedAt ? `마지막 수신 ${kst(connectedAt).slice(11, 19)}` : "수신 전"}
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
            장애 시연 중 · {activeFaults.map((code) => FAULTS[code]).join(" / ")}
          </div>
        )}
        {!state.running && <div className="qc-warning">입력 정지 상태</div>}
      </div>
      <nav className="qc-admin-tabs" aria-label="관리 메뉴">
        {TABS.map(([key, label]) => (
          <button key={key} aria-pressed={tab === key} onClick={() => setTab(key)}>
            {label}
            {key === "images" && ` ${imageCount}장`}
          </button>
        ))}
      </nav>
      <section className="qc-admin-body" aria-label={TABS.find(([key]) => key === tab)?.[1]}>
        {tab === "history" && (
          <QualityHistory
            records={state.history}
            remote={remote}
            allowReview={!remote || !!snapshot?.capabilities.review}
            classify={classify}
          />
        )}
        {tab === "statistics" && (
          <>
            <div className="qc-actions qc-admin-export">
              <span>오늘 집계·최근 구간 CSV</span>
              <label>
                최근 구간{" "}
                <select
                  aria-label="통계 CSV 구간"
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
              <button onClick={exportStats}>통계 CSV</button>
            </div>
            <QualityStatistics
              remote={remote}
              records={state.history}
              reference={!remote || snapshot?.source === "reference"}
            />
          </>
        )}
        {tab === "images" && (
          <FaultImages
            images={faultImages}
            imageSource={faultImageSource}
            retained={imageCount}
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
        {tab === "settings" && (
          <>
            <p>
              {remote
                ? "서버가 허용한 설정만 조작할 수 있습니다. 응답 성공 후 적용됩니다."
                : "브라우저 예시 시연입니다. 새로고침하면 설정이 초기화됩니다."}
            </p>
            <div className="qc-actions">
              <button
                className="qc-run"
                disabled={disabled || !allowControl}
                onClick={() => action(configure({ running: !state.running }))}
              >
                {state.running ? "입력 정지" : "입력 재개"}
              </button>
              <label>
                라인 속도{" "}
                <select
                  aria-label="라인 속도"
                  value={state.intervalMs ?? ""}
                  disabled={disabled || !allowSpeed}
                  onChange={(event) =>
                    action(configure({ intervalMs: Number(event.target.value) }))
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
                    action(configure({ concurrency: Number(event.target.value) }))
                  }
                >
                  {(remote ? (snapshot?.capabilities.concurrency ?? []) : [1, 2, 4]).map(
                    (value) => (
                      <option key={value} value={value}>
                        {value === 1 ? "순차 1개" : `병렬 ${value}개`}
                      </option>
                    ),
                  )}
                </select>
              </label>
              <label>
                적용 범위{" "}
                <select
                  aria-label="장애 적용 범위"
                  value={state.scope ?? ""}
                  disabled={disabled || !allowFaults}
                  onChange={(event) =>
                    action(configure({ scope: event.target.value as Runtime["scope"] }))
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
      </section>
    </main>
  );
}
