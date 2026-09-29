"use client";
import { useEffect, useState } from "react";
import { qualityRequest, downloadQualityCsv } from "@/lib/quality-api";
import {
  summarizeInspections,
  type InspectionSummary,
} from "@/lib/quality-statistics";
import { csvCell, kst, type Result } from "@/lib/quality-runtime";
import { MISCLASSIFICATION_LABEL } from "@/lib/quality-contract";

export default function QualityStatistics({
  remote,
  records,
  reference,
}: {
  remote: boolean;
  records: Result[];
  reference: boolean;
}) {
  const [snapshotRecords] = useState(records);
  const [from, setFrom] = useState(() => kst(Date.now()).slice(0, 10)),
    [to, setTo] = useState(from);
  const [reload, setReload] = useState(0);
  const [summary, setSummary] = useState<InspectionSummary | null>(null);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(remote);
  const invalid = !from || !to || from > to;
  const local = summarizeInspections(
    snapshotRecords.filter((row) => row.date >= from && row.date <= to),
  );
  const data = remote ? summary : local;
  useEffect(() => {
    if (!remote || invalid) return;
    const controller = new AbortController();
    let active = true;
    void Promise.resolve().then(async () => {
      if (!active) return;
      setLoading(true);
      setStatus("");
      try {
        const response = await qualityRequest(
          `statistics?from=${from}&to=${to}`,
          {
            signal: AbortSignal.any([
              controller.signal,
              AbortSignal.timeout(8000),
            ]),
          },
        );
        const value = await response.json();
        if (
          !value ||
          typeof value.total !== "number" ||
          ![
            "total",
            "normal",
            "excluded",
            "reinspection",
            "inferenceTotalMs",
            "inferenceCount",
          ].every((key) => Number.isFinite(value[key]) && value[key] >= 0) ||
          !["varieties", "grades", "bins", "suspicions"].every(
            (key) =>
              value[key] &&
              typeof value[key] === "object" &&
              Object.values(value[key]).every(
                (n) => typeof n === "number" && Number.isFinite(n) && n >= 0,
              ),
          )
        )
          throw new Error("통계 응답 형식이 올바르지 않습니다.");
        if (active) setSummary(value);
      } catch (cause) {
        if (active) {
          setStatus(cause instanceof Error ? cause.message : "조회 실패");
          setSummary(null);
        }
      } finally {
        if (active) setLoading(false);
      }
    });
    return () => {
      active = false;
      controller.abort();
    };
  }, [remote, from, to, reload, invalid]);
  async function exportCsv() {
    try {
      if (remote)
        await downloadQualityCsv(
          `statistics.csv?from=${from}&to=${to}`,
          "cqc-period-statistics.csv",
        );
      else {
        const rows: unknown[][] = [
          ["from_kst", "to_kst", "group", "key", "value"],
        ];
        for (const [key, value] of Object.entries(local))
          if (typeof value === "number")
            rows.push([from, to, "total", key, value]);
          else
            for (const [name, count] of Object.entries(value))
              rows.push([from, to, key, name, count]);
        const url = URL.createObjectURL(
          new Blob(
            [
              "\uFEFF" +
                rows.map((row) => row.map(csvCell).join(",")).join("\r\n"),
            ],
            { type: "text/csv;charset=utf-8" },
          ),
        );
        const link = document.createElement("a");
        link.href = url;
        link.download = "cqc-demo-period-statistics.csv";
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
      setStatus("CSV 다운로드를 요청했습니다.");
    } catch (cause) {
      setStatus(cause instanceof Error ? cause.message : "CSV 실패");
    }
  }
  return (
    <section>
      <div className="qc-actions">
        <label>
          통계 시작일
          <input
            type="date"
            value={from}
            onInput={(e) => setFrom(e.currentTarget.value)}
            onChange={(e) => setFrom(e.target.value)}
          />
        </label>
        <label>
          통계 종료일
          <input
            type="date"
            value={to}
            onInput={(e) => setTo(e.currentTarget.value)}
            onChange={(e) => setTo(e.target.value)}
          />
        </label>
        {remote && (
          <button
            disabled={invalid || loading}
            onClick={() => setReload((n) => n + 1)}
          >
            통계 새로고침
          </button>
        )}
        <button disabled={invalid || loading || !data} onClick={exportCsv}>
          기간 통계 CSV
        </button>
      </div>
      <p className="qc-muted">
        KST 날짜 기준 · 현재 보존 중인 이력만 집계합니다. 보존 기간 이전 기록은
        포함되지 않습니다.{reference && " 참조 시연 수치입니다."}
      </p>
      {invalid && <p role="alert">시작일과 종료일을 올바르게 선택하세요.</p>}
      <p role="status">{loading ? "통계를 불러오는 중입니다." : status}</p>
      {!invalid && !loading && data && (
        <>
          <div className="qc-summary-grid">
            <div>
              전체 검사<strong>{data.total}건</strong>
            </div>
            <div>
              재검사
              <strong>
                {data.reinspection}건 ·{" "}
                {data.total
                  ? ((data.reinspection / data.total) * 100).toFixed(1)
                  : "0.0"}
                %
              </strong>
            </div>
            <div>
              평균 추론
              <strong>
                {data.inferenceCount
                  ? `${(data.inferenceTotalMs / data.inferenceCount).toFixed(1)}ms`
                  : "—"}
              </strong>
            </div>
            <div>
              통계 제외<strong>{data.excluded}건</strong>
            </div>
          </div>
          {(
            [
              ["varieties", "품종", data.normal],
              ["grades", "품질", data.normal],
              [
                "bins",
                "성공한 선별 명령",
                Object.values(data.bins).reduce((a, b) => a + b, 0),
              ],
              ["suspicions", "오판 의심", data.total],
            ] as const
          ).map(([key, label, denominator]) => (
            <section key={key}>
              <h3>{label}</h3>
              <table>
                <thead>
                  <tr>
                    <th>분류</th>
                    <th>수량</th>
                    <th>비율</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(data[key]).map(([name, count]) => (
                    <tr key={name}>
                      <td>
                        {key === "suspicions"
                          ? MISCLASSIFICATION_LABEL[
                              name as keyof typeof MISCLASSIFICATION_LABEL
                            ]
                          : name}
                      </td>
                      <td>{count}건</td>
                      <td>
                        {denominator
                          ? ((count / denominator) * 100).toFixed(1)
                          : "0.0"}
                        %
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ))}
        </>
      )}
    </section>
  );
}
