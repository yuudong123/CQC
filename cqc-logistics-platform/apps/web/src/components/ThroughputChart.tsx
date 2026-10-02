"use client";

import {
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
  type ChartData,
  type ChartOptions,
} from "chart.js";
import { Line } from "react-chartjs-2";
import { kst, type ThroughputPoint } from "@/lib/quality-runtime";

ChartJS.register(LinearScale, LineElement, PointElement, Filler, Tooltip, Legend);

type Point = { x: number; y: number | null; label?: string };
export type ChartEvent = { at: number; kind: "reinspection" | "error"; reason: string };

const INK = "#34232c";
const MUTED = "#8c7e84";
const GRID = "#f1e8e9";
const ROSE = "#ae525c";
const REVIEW = "#d98b1f";
const ERROR = "#c01c31";

/** 최근 처리량 선 + 설정 라인 속도 점선 + 재검사·오류 시점 점. x는 현재 기준 초(음수)다. */
export default function ThroughputChart({
  series,
  end,
  target,
  events,
  minutes,
}: {
  series: ThroughputPoint[];
  end: number;
  target: number | null;
  events: ChartEvent[];
  minutes: number;
}) {
  const span = minutes * 60;
  const x = (at: number) => (at - end) / 1000;
  const peak = Math.max(0, ...series.map((point) => point.value ?? 0));
  const top = Math.max(1, (target ?? 0) * 1.5, peak * 1.2);
  const marks = (kind: ChartEvent["kind"]): Point[] =>
    events
      .filter((event) => event.kind === kind && x(event.at) >= -span)
      .map((event) => ({ x: x(event.at), y: 0, label: event.reason }));
  const data: ChartData<"line", Point[]> = {
    datasets: [
      {
        label: "처리량",
        data: series.map((point) => ({ x: x(point.at), y: point.value })),
        borderColor: ROSE,
        backgroundColor: "rgba(174, 82, 92, 0.12)",
        borderWidth: 2,
        fill: "origin",
        tension: 0.3,
        pointRadius: 0,
        pointHoverRadius: 4,
        spanGaps: false,
      },
      ...(target === null
        ? []
        : [
            {
              label: "설정 라인 속도",
              data: [
                { x: -span, y: target },
                { x: 0, y: target },
              ],
              borderColor: MUTED,
              borderWidth: 1.5,
              borderDash: [5, 4],
              pointRadius: 0,
              pointHoverRadius: 0,
            },
          ]),
      {
        label: "재검사",
        data: marks("reinspection"),
        showLine: false,
        clip: false,
        pointStyle: "circle",
        pointRadius: 4,
        pointHoverRadius: 6,
        backgroundColor: REVIEW,
        borderColor: "#ffffff",
        borderWidth: 1.5,
      },
      {
        label: "오류",
        data: marks("error"),
        showLine: false,
        clip: false,
        pointStyle: "triangle",
        pointRadius: 5,
        pointHoverRadius: 7,
        backgroundColor: ERROR,
        borderColor: "#ffffff",
        borderWidth: 1.5,
      },
    ],
  };
  const options: ChartOptions<"line"> = {
    animation: false,
    maintainAspectRatio: false,
    parsing: false,
    normalized: true,
    interaction: { mode: "nearest", axis: "x", intersect: false },
    layout: { padding: { top: 4 } },
    scales: {
      x: {
        type: "linear",
        min: -span,
        max: 0,
        grid: { display: false },
        border: { color: GRID },
        ticks: {
          color: MUTED,
          font: { size: 11 },
          stepSize: span / 5,
          callback: (value) =>
            Number(value) === 0
              ? "현재"
              : Number(value) % 60 === 0
                ? `${-Number(value) / 60}분 전`
                : `${-Number(value)}초 전`,
        },
      },
      y: {
        min: 0,
        max: Number(top.toFixed(1)),
        grid: { color: GRID },
        border: { display: false },
        ticks: { color: MUTED, font: { size: 11 }, maxTicksLimit: 4 },
        title: { display: true, text: "건/초", color: MUTED, font: { size: 11 } },
      },
    },
    plugins: {
      legend: {
        position: "bottom",
        labels: {
          color: INK,
          font: { size: 11 },
          usePointStyle: true,
          boxWidth: 8,
          boxHeight: 8,
          padding: 10,
        },
      },
      tooltip: {
        displayColors: true,
        callbacks: {
          title: (items) =>
            items.length ? kst(end + (items[0].parsed.x ?? 0) * 1000).slice(11, 19) : "",
          label: (item) => {
            const point = item.raw as Point;
            if (item.dataset.label === "처리량")
              return point.y === null ? "처리량 수집 전" : `처리량 ${point.y.toFixed(2)}건/초`;
            if (item.dataset.label === "설정 라인 속도")
              return `설정 라인 속도 ${target?.toFixed(2)}건/초`;
            return `${item.dataset.label} · ${point.label}`;
          },
        },
      },
    },
  };
  return (
    <div
      className="qc-trend"
      role="img"
      aria-label={`최근 ${minutes}분 처리량 추이. 현재 ${(series.at(-1)?.value ?? 0).toFixed(2)}건/초${target === null ? "" : `, 설정 라인 속도 ${target.toFixed(2)}건/초`}, 재검사 ${marks("reinspection").length}건, 오류 ${marks("error").length}건`}
    >
      <Line data={data} options={options} />
    </div>
  );
}
