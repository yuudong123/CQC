"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  getHistory,
  historyQuery,
  downloadQualityCsv,
  type HistoryPage,
} from "@/lib/quality-api";
import { Badge } from "./Dashboard";
import {
  DEFAULT_QUALITY_FILTERS,
  ERROR_LABEL,
  MISCLASSIFICATION_LABEL,
  PAGE_SIZES,
  PROCESSING_STATUS_LABEL,
  type QualityFilterState,
  type MisclassificationType,
} from "@/lib/quality-contract";
import { csvCell, type Result } from "@/lib/quality-runtime";

export default function QualityHistory({
  records: latestRecords,
  classify,
  remote = false,
  allowReview = true,
}: {
  records: Result[];
  classify: (id: string, value: MisclassificationType) => Promise<void>;
  remote?: boolean;
  allowReview?: boolean;
}) {
  const [records, setRecords] = useState(latestRecords);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<QualityFilterState>(
    DEFAULT_QUALITY_FILTERS,
  );
  const [message, setMessage] = useState("");
  const [serverPage, setServerPage] = useState<HistoryPage | null>(null);
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(remote);
  const [loadError, setLoadError] = useState("");
  const [saving, setSaving] = useState(false);
  const anchor = useRef<number | undefined>(undefined);
  const invalidDate = Boolean(
    filters.from && filters.to && filters.from > filters.to,
  );
  const filtered = useMemo(
    () =>
      remote
        ? (serverPage?.items ?? [])
        : records.filter(
            (row) =>
              (!filters.from || row.date >= filters.from) &&
              (!filters.to || row.date <= filters.to) &&
              (filters.variety === "ALL" ||
                (!row.excluded && row.variety === filters.variety)) &&
              (filters.grade === "ALL" ||
                (!row.excluded && row.grade === filters.grade)) &&
              (filters.bin === "ALL" || row.bin === filters.bin) &&
              (filters.processingStatus === "ALL" ||
                row.processingStatus === filters.processingStatus) &&
              (filters.errorCode === "ALL" ||
                (filters.errorCode === "NONE"
                  ? !row.faults.length
                  : row.faults.includes(filters.errorCode))) &&
              (filters.misclassification === "ALL" ||
                row.misclassification === filters.misclassification),
          ),
    [filters, records, remote, serverPage],
  );
  const total = remote ? (serverPage?.total ?? 0) : filtered.length;
  const pages = Math.max(1, Math.ceil(total / filters.pageSize));
  const currentPage = Math.min(page, pages);
  useEffect(() => {
    if (!remote || invalidDate) return;
    const controller = new AbortController();
    let active = true;
    // Start asynchronously to keep effects limited to external synchronization.
    void Promise.resolve().then(async () => {
      if (!active) return;
      setLoading(true);
      setLoadError("");
      try {
        const result = await getHistory(
          filters,
          page,
          anchor.current,
          AbortSignal.any([controller.signal, AbortSignal.timeout(8000)]),
        );
        if (active) {
          anchor.current = result.snapshotAt;
          setServerPage(result);
          if (page > Math.max(1, Math.ceil(result.total / filters.pageSize))) setPage(Math.max(1, Math.ceil(result.total / filters.pageSize)));
        }
      } catch (cause) {
        if (active)
          setLoadError(
            cause instanceof Error ? cause.message : "이력 조회 실패",
          );
      } finally {
        if (active) setLoading(false);
      }
    });
    return () => {
      active = false;
      controller.abort();
    };
  }, [remote, filters, page, reload, invalidDate]);
  function filter<K extends keyof QualityFilterState>(
    key: K,
    value: QualityFilterState[K],
  ) {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(1);
  }
  function exportCsv() {
    if (remote) {
      setSaving(true);
      void downloadQualityCsv(
        `inspections.csv?${historyQuery(filters, 1, anchor.current)}`,
        "cqc-inspections.csv",
      )
        .then(() => setMessage(`${total}건 CSV 다운로드를 요청했습니다.`))
        .catch((cause) => setMessage(cause.message))
        .finally(() => setSaving(false));
      return;
    }
    const columns = [
      "inspection_id",
      "date",
      "time_kst",
      "variety",
      "grade",
      "confidence",
      "cultivar_confidence",
      "inference_ms",
      "model_version",
      "target_bin",
      "inspection_status",
      "processing_status",
      "control_status",
      "persistence_status",
      "error_codes",
      "misclassification",
      "virtual_brix",
      "brix_is_measured",
    ];
    const rows = filtered.map((row) => [
      row.id,
      row.date,
      row.time,
      row.excluded ? "" : row.variety,
      row.excluded ? "" : row.grade,
      row.excluded ? "" : row.confidence,
      row.cultivarConfidence,
      row.inferenceMs,
      row.modelVersion,
      row.bin,
      row.status,
      row.processingStatus,
      row.control,
      row.persistence,
      row.faults.join("|"),
      row.misclassification,
      row.virtualBrix,
      false,
    ]);
    const url = URL.createObjectURL(
      new Blob(
        [
          "\uFEFF" +
            [columns, ...rows]
              .map((row) => row.map(csvCell).join(","))
              .join("\r\n"),
        ],
        { type: "text/csv;charset=utf-8" },
      ),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "cqc-demo-inspections.csv";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
    setMessage(`${filtered.length}건을 CSV로 내보냈습니다.`);
  }
  return (
    <section className="quality-history">
      <div className="qc-actions">
        <strong>{total}건 검색</strong>
        <button
          onClick={() => {
            setRecords(latestRecords);
            anchor.current = undefined;
            setReload((value) => value + 1);
            setPage(1);
            setMessage("최신 이력을 불러왔습니다.");
          }}
        >
          목록 새로고침
        </button>
        <button
          onClick={() => {
            setFilters(DEFAULT_QUALITY_FILTERS);
            setPage(1);
            setMessage("");
          }}
        >
          초기화
        </button>
        <button
          onClick={exportCsv}
          disabled={invalidDate || !total || loading || !!loadError || saving}
        >
          CSV 내보내기
        </button>
        <button
          disabled={currentPage === 1 || loading}
          onClick={() => setPage(currentPage - 1)}
        >
          이전 페이지
        </button>
        <span>
          {currentPage} / {pages}페이지
        </span>
        <button
          disabled={currentPage === pages || loading}
          onClick={() => setPage(currentPage + 1)}
        >
          다음 페이지
        </button>
      </div>
      <p className="qc-muted">
        {remote
          ? "서버 보관 이력을 조회합니다. 목록 새로고침 전까지 조회 기준 시각을 유지합니다."
          : "목록을 연 시점의 예시 이력입니다. 최신 2,000건은 목록 새로고침으로 불러옵니다."}{" "}
        CSV에는 페이지와 관계없이 필터 결과 전체가 포함되며 이미지는 포함되지
        않습니다.
      </p>
      <div className="history-filters">
        <label>
          시작일
          <input
            type="date"
            value={filters.from}
            onInput={(event) => filter("from", event.currentTarget.value)}
            onChange={(event) => filter("from", event.target.value)}
          />
        </label>
        <label>
          종료일
          <input
            type="date"
            value={filters.to}
            onInput={(event) => filter("to", event.currentTarget.value)}
            onChange={(event) => filter("to", event.target.value)}
          />
        </label>
        <label>
          품종
          <select
            aria-label="품종"
            value={filters.variety}
            onChange={(event) =>
              filter(
                "variety",
                event.target.value as QualityFilterState["variety"],
              )
            }
          >
            <option value="ALL">전체</option>
            {["부사", "양광"].map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </label>
        <label>
          품질
          <select
            aria-label="품질"
            value={filters.grade}
            onChange={(event) =>
              filter("grade", event.target.value as QualityFilterState["grade"])
            }
          >
            <option value="ALL">전체</option>
            {["특", "상", "보통"].map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </label>
        <label>
          선별함
          <select
            aria-label="선별함"
            value={filters.bin}
            onChange={(event) => filter("bin", event.target.value)}
          >
            <option value="ALL">전체</option>
            {(remote
              ? (serverPage?.bins ?? [])
              : [...new Set(records.map((row) => row.bin))]
            ).map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </label>
        <label>
          처리 상태
          <select
            aria-label="처리 상태"
            value={filters.processingStatus}
            onChange={(event) =>
              filter(
                "processingStatus",
                event.target.value as QualityFilterState["processingStatus"],
              )
            }
          >
            <option value="ALL">전체</option>
            {Object.entries(PROCESSING_STATUS_LABEL).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          오류 유형
          <select
            aria-label="오류 유형"
            value={filters.errorCode}
            onChange={(event) =>
              filter(
                "errorCode",
                event.target.value as QualityFilterState["errorCode"],
              )
            }
          >
            <option value="ALL">전체</option>
            {Object.entries(ERROR_LABEL).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          오판 의심
          <select
            aria-label="오판 의심"
            value={filters.misclassification}
            onChange={(event) =>
              filter(
                "misclassification",
                event.target.value as QualityFilterState["misclassification"],
              )
            }
          >
            <option value="ALL">전체</option>
            {Object.entries(MISCLASSIFICATION_LABEL).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          표시 행 수
          <select
            aria-label="표시 행 수"
            value={filters.pageSize}
            onChange={(event) =>
              filter(
                "pageSize",
                Number(event.target.value) as QualityFilterState["pageSize"],
              )
            }
          >
            {PAGE_SIZES.map((value) => (
              <option key={value} value={value}>
                {value}건
              </option>
            ))}
          </select>
        </label>
      </div>
      {invalidDate && <p role="alert">시작일은 종료일보다 늦을 수 없습니다.</p>}
      {loading && <p role="status">이력을 불러오는 중입니다.</p>}
      {loadError && (
        <p role="alert">
          {loadError} 이전 조회 결과를 유지합니다. 목록 새로고침으로 다시
          시도하세요.
        </p>
      )}
      <p role="status">{message}</p>
      <table>
        <thead>
          <tr>
            <th>시각 (KST)</th>
            <th>검사 ID</th>
            <th>품종 / 등급</th>
            <th>품종 / 품질 신뢰도</th>
            <th>추론 / 모델</th>
            <th>가상 °Brix (비실측)</th>
            <th>상태</th>
            <th>BIN</th>
            <th>제어</th>
            <th>저장</th>
            <th>오판 의심</th>
          </tr>
        </thead>
        <tbody>
          {(remote
            ? filtered
            : filtered.slice(
                (currentPage - 1) * filters.pageSize,
                currentPage * filters.pageSize,
              )
          ).map((row) => (
            <tr key={row.id}>
              <td>
                {row.date} {row.time}
              </td>
              <td>{row.id}</td>
              <td>{row.excluded ? "—" : `${row.variety} / ${row.grade}`}</td>
              <td>
                {row.excluded
                  ? "—"
                  : `${row.cultivarConfidence ?? "—"}% / ${row.confidence}%`}
              </td>
              <td>
                {row.inferenceMs === null ? "—" : `${row.inferenceMs}ms`} /{" "}
                {row.modelVersion ?? "—"}
              </td>
              <td>{row.virtualBrix?.toFixed(1) ?? "—"}</td>
              <td>
                <Badge
                  tone={
                    row.excluded
                      ? "danger"
                      : row.status === "REVIEW"
                        ? "warning"
                        : "success"
                  }
                >
                  {PROCESSING_STATUS_LABEL[row.processingStatus]}
                  {row.status === "REVIEW" && " · 검수"}
                </Badge>
              </td>
              <td>{row.bin}</td>
              <td>
                {row.control === "NO_RESPONSE"
                  ? "무응답"
                  : row.control === "NOT_REQUESTED"
                    ? "미요청"
                  : row.control === "FALLBACK"
                    ? "재검사 대체 1회"
                    : row.control === "REJECTED"
                      ? "거부"
                      : row.control === "FAILED"
                        ? "실패"
                        : "성공"}
              </td>
              <td>{row.persistence === "SAVED" ? "완료" : "실패"}</td>
              <td>
                <select
                  aria-label={`${row.id} 오판 의심`}
                  value={row.misclassification}
                  disabled={saving || loading || !!loadError || !allowReview}
                  onChange={async (event) => {
                    const value = event.target.value as MisclassificationType;
                    setSaving(true);
                    try {
                      await classify(row.id, value);
                      setRecords((current) =>
                        current.map((item) =>
                          item.id === row.id
                            ? { ...item, misclassification: value }
                            : item,
                        ),
                      );
                      if (remote) setReload((v) => v + 1);
                      setMessage("오판 의심 표시를 저장했습니다.");
                    } catch (cause) {
                      setMessage(
                        cause instanceof Error ? cause.message : "저장 실패",
                      );
                    } finally {
                      setSaving(false);
                    }
                  }}
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
            </tr>
          ))}
        </tbody>
      </table>
      {!filtered.length && (
        <p className="qc-empty">조건에 맞는 이력이 없습니다.</p>
      )}
    </section>
  );
}
