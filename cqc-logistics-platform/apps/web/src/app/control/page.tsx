"use client";

import { useCallback, useEffect, useState } from "react";
import GoogleFleetMap from "@/components/GoogleFleetMap";
import {
  Badge,
  Empty,
  Icon,
  Panel,
  Progress,
  Stats,
} from "@/components/Dashboard";
import { logisticsFetch, logisticsLive } from "@/lib/logistics-client";

type Point = { type: "Point"; coordinates: [number, number] };
type Fleet = {
  fleetId: string;
  name: string;
  capacityKg: number;
  currentLoadKg: number;
  status: string;
  location: Point;
};
type Stop = {
  sequence: number;
  type: string;
  status: string;
  orderId: string;
  location: Point;
};
type Route = {
  routeId: string;
  fleetId: string;
  version: number;
  status: string;
  stops: Stop[];
  estimatedMinutes: number;
};
type Alert = {
  alertId: string;
  severity: string;
  title: string;
  message: string;
  createdAt: string;
};
type Overview = {
  fleets: Fleet[];
  routes: Route[];
  alerts: Alert[];
  generatedAt: string;
  stats: {
    openAuctions: number;
    activeFleets: number;
    inTransitOrders: number;
    attentionRequired: number;
  };
};
const statusLabel = (status: string) =>
  ({
    IDLE: "대기",
    TO_PICKUP: "픽업 이동",
    WAITING_LOAD: "상차 대기",
    IN_TRANSIT: "배송 중",
    WAITING_UNLOAD: "하차 대기",
    OUT_OF_SERVICE: "고장 격리",
  })[status] ?? status;
const statusTone = (status: string) =>
  ({
    IDLE: "neutral",
    TO_PICKUP: "blue",
    WAITING_LOAD: "warning",
    IN_TRANSIT: "success",
    WAITING_UNLOAD: "warning",
    OUT_OF_SERVICE: "danger",
  })[status] ?? "neutral";
const stopLabel = (status: string) =>
  ({ PENDING: "이동 예정", ARRIVED: "도착 · 확인 대기", COMPLETED: "완료" })[
    status
  ] ?? status;

export default function ControlPage() {
  const [data, setData] = useState<Overview>();
  const [selectedId, setSelectedId] = useState<string>();
  const [message, setMessage] = useState("");
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [allAlerts, setAllAlerts] = useState(false);
  const fleets = data?.fleets ?? [];
  const selected = fleets.find((fleet) => fleet.fleetId === selectedId);
  const route = data?.routes.find(
    (item) => item.fleetId === selectedId && item.status === "ACTIVE",
  );
  const nextStop = route?.stops.find((stop) => stop.status !== "COMPLETED");
  const alerts = data?.alerts ?? [];

  const loadOverview = useCallback(async (signal?: AbortSignal) => {
    try {
      const response = await logisticsFetch("/control/overview", {
        cache: "no-store",
        signal,
      });
      if (!response.ok) throw new Error();
      const overview = (await response.json()) as Overview;
      setData(overview);
      setConnected(true);
      setSelectedId((current) =>
        overview.fleets.some((fleet) => fleet.fleetId === current)
          ? current
          : overview.fleets[0]?.fleetId,
      );
    } catch {
      if (!signal?.aborted) setConnected(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const initial = window.setTimeout(
      () => void loadOverview(controller.signal),
      0,
    );
    const timer = window.setInterval(
      () => void loadOverview(controller.signal),
      2000,
    );
    return () => {
      controller.abort();
      clearTimeout(initial);
      clearInterval(timer);
    };
  }, [loadOverview]);

  async function action(path: string, success: string) {
    setBusy(true);
    try {
      const response = await logisticsFetch(path, { method: "POST" });
      const result = (await response.json().catch(() => null)) as {
        detail?: string;
      } | null;
      if (!response.ok)
        throw new Error(result?.detail ?? "요청에 실패했습니다.");
      setMessage(success);
      await loadOverview();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "서버에 연결할 수 없습니다.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="dashboard control-page">
      <Stats
        items={[
          {
            label: "공개 경매",
            value: data ? `${data.stats.openAuctions}건` : "—",
            icon: "market",
          },
          {
            label: "운행 차량",
            value: data ? `${data.stats.activeFleets}대` : "—",
            icon: "truck",
          },
          {
            label: "배송 중 주문",
            value: data ? `${data.stats.inTransitOrders}건` : "—",
            icon: "box",
          },
          {
            label: "확인 필요",
            value: data ? `${data.stats.attentionRequired}건` : "—",
            icon: "alert",
          },
        ]}
      />
      <div className="control-toolbar">
        <Badge tone={connected ? "success" : "warning"}>
          {connected ? (logisticsLive ? "● 실시간 연결" : "● 시연용 가상 물류") : "서버 연결 대기"}
        </Badge>
        <span className="muted">
          {connected
            ? `최종 업데이트 ${new Date(data!.generatedAt).toLocaleTimeString("ko-KR", { hour12: false })}`
            : "관제 서버에 자동으로 다시 연결합니다."}
        </span>
        <button
          className="text-button"
          disabled={busy || !connected}
          type="button"
          onClick={() =>
            void action(
              "/control/seed-reset",
              "발표용 샘플 상태로 초기화했습니다.",
            )
          }
        >
          발표 상태 초기화
        </button>
      </div>
      {message && (
        <div className="page-notice" role="status">
          {message}
        </div>
      )}
      <div className="control-workspace">
        <Panel title="차량 현황" action={<small>총 {fleets.length}대</small>}>
          <div className="fleet-list">
            {fleets.map((fleet) => (
              <button
                type="button"
                className={`fleet-card ${selectedId === fleet.fleetId ? "selected" : ""}`}
                onClick={() => setSelectedId(fleet.fleetId)}
                key={fleet.fleetId}
                aria-pressed={selectedId === fleet.fleetId}
                disabled={busy}
              >
                <div className="fleet-card-head">
                  <span className="vehicle-icon">
                    <Icon name="truck" />
                  </span>
                  <strong>{fleet.name}</strong>
                  <Badge tone={statusTone(fleet.status)}>
                    {statusLabel(fleet.status)}
                  </Badge>
                  <span className="chevron">›</span>
                </div>
                <div className="load-meter">
                  <small>적재량</small>
                  <Progress
                    value={(fleet.currentLoadKg / fleet.capacityKg) * 100}
                    label={`${fleet.name} 적재율`}
                  />
                  <span>
                    {fleet.currentLoadKg.toLocaleString()} /{" "}
                    {fleet.capacityKg.toLocaleString()}kg
                  </span>
                </div>
              </button>
            ))}
          </div>
          {!fleets.length && (
            <Empty>
              {connected
                ? "등록된 차량이 없습니다."
                : "차량 데이터를 기다리고 있습니다."}
            </Empty>
          )}
        </Panel>
        <Panel
          title="실시간 차량 위치와 경로"
          action={<small>↻ 2초마다 갱신</small>}
          className="control-map-panel"
        >
          <GoogleFleetMap
            fleets={fleets}
            stops={
              route?.stops.map((stop) => ({
                label: stop.type === "PICKUP" ? "픽업" : "하차",
                location: stop.location,
              })) ?? []
            }
          />
        </Panel>
        <Panel title="선택 차량 상세" action={<small>GPS 시뮬레이터</small>}>
          {selected ? (
            <>
              <div className="selected-fleet">
                <span className="vehicle-icon">
                  <Icon name="truck" />
                </span>
                <h3>{selected.name}</h3>
                <Badge tone={statusTone(selected.status)}>
                  {statusLabel(selected.status)}
                </Badge>
              </div>
              <div className="load-meter detail-load">
                <small>적재량</small>
                <Progress
                  value={(selected.currentLoadKg / selected.capacityKg) * 100}
                  label="선택 차량 적재율"
                />
                <span>
                  {selected.currentLoadKg.toLocaleString()} /{" "}
                  {selected.capacityKg.toLocaleString()}kg
                </span>
              </div>
              <dl className="fleet-details">
                <dt>
                  <Icon name="pin" />
                  다음 목적지
                </dt>
                <dd>
                  {nextStop
                    ? `${nextStop.sequence}번 ${nextStop.type === "PICKUP" ? "픽업지" : "배송지"}`
                    : "배정된 경유지 없음"}
                </dd>
                <dt>
                  <Icon name="clock" />
                  예상 소요 시간
                </dt>
                <dd>
                  {route ? `${Math.round(route.estimatedMinutes)}분` : "—"}
                </dd>
                <dt>
                  <Icon name="document" />
                  노선 버전
                </dt>
                <dd>{route ? `v${route.version}` : "—"}</dd>
              </dl>
              <div className="control-actions">
                <button
                  className="primary-button"
                  type="button"
                  disabled={
                    busy ||
                    !connected ||
                    !route ||
                    !["TO_PICKUP", "IN_TRANSIT"].includes(selected.status)
                  }
                  onClick={() =>
                    void action(
                      `/fleets/${selected.fleetId}/simulate-step`,
                      "차량을 다음 경유지 방향으로 이동했습니다.",
                    )
                  }
                >
                  <Icon name="arrow" />
                  다음 위치로 이동
                </button>
                <button
                  className="outline-button danger"
                  type="button"
                  disabled={
                    busy || !connected || selected.status === "OUT_OF_SERVICE"
                  }
                  onClick={() =>
                    void action(
                      `/fleets/${selected.fleetId}/breakdown`,
                      "차량 고장 처리 및 대체배차 결과를 갱신했습니다.",
                    )
                  }
                >
                  <Icon name="alert" />
                  차량 고장 시뮬레이션
                </button>
              </div>
              <div className="notice-box">
                시뮬레이션 전용 기능으로 실제 차량에 영향을 주지 않습니다.
              </div>
            </>
          ) : (
            <Empty>왼쪽에서 차량을 선택해 주세요.</Empty>
          )}
        </Panel>
      </div>
      <div className="control-bottom">
        <Panel
          title="배송 경로"
          action={
            <small>
              {selected?.name ?? "차량 선택 대기"}
              {route ? ` · 총 ${route.stops.length}개 경유지` : ""}
            </small>
          }
        >
          {route ? (
            <div className="route-timeline">
              {route.stops.map((stop) => (
                <div
                  className={`route-stop ${stop.status.toLowerCase()}`}
                  key={`${stop.orderId}-${stop.sequence}`}
                >
                  <span className="stop-number">
                    {stop.status === "COMPLETED" ? "✓" : stop.sequence}
                  </span>
                  <div>
                    <strong>
                      {stop.type === "PICKUP" ? "픽업지" : "배송지"}{" "}
                      {stop.sequence}
                    </strong>
                    <small>{stop.orderId}</small>
                    <Badge
                      tone={
                        stop.status === "COMPLETED"
                          ? "success"
                          : stop.status === "ARRIVED"
                            ? "warning"
                            : "neutral"
                      }
                    >
                      {stopLabel(stop.status)}
                    </Badge>
                  </div>
                  <Icon name="arrow" />
                </div>
              ))}
            </div>
          ) : (
            <Empty>선택한 차량에 배정된 배송 경로가 없습니다.</Empty>
          )}
        </Panel>
        <Panel
          title="장애 알림"
          icon="alert"
          action={
            <button
              type="button"
              className="text-button"
              onClick={() => setAllAlerts(!allAlerts)}
            >
              {allAlerts ? "접기" : `전체 보기 (${alerts.length})`} ›
            </button>
          }
        >
          {alerts.length ? (
            <div className="alert-list">
              {alerts.slice(0, allAlerts ? undefined : 2).map((alert) => (
                <article
                  className={`alert-row ${alert.severity.toLowerCase()}`}
                  key={alert.alertId}
                >
                  <Icon name="alert" />
                  <div>
                    <strong>{alert.title}</strong>
                    <p>{alert.message}</p>
                  </div>
                  <time>
                    {new Date(alert.createdAt).toLocaleTimeString("ko-KR", {
                      hour: "2-digit",
                      minute: "2-digit",
                      hour12: false,
                    })}
                  </time>
                </article>
              ))}
            </div>
          ) : (
            <Empty>
              <Icon name="check" />
              {connected
                ? "현재 확인이 필요한 알림이 없습니다."
                : "연결 후 장애 상태를 확인할 수 있습니다."}
            </Empty>
          )}
        </Panel>
      </div>
    </main>
  );
}
