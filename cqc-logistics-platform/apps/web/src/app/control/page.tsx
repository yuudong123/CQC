"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import GoogleFleetMap from "@/components/GoogleFleetMap";

type Point = { type: "Point"; coordinates: [number, number] };
type Fleet = {
  fleetId: string;
  name: string;
  capacityKg: number;
  currentLoadKg: number;
  status: string;
  location: Point;
};
type Stop = { sequence: number; type: string; status: string; orderId: string; location: Point };
type Route = { routeId: string; version: number; status: string; stops: Stop[] };
type Alert = { alertId: string; severity: string; title: string; message: string; createdAt: string };
type Stats = { openAuctions: number; activeFleets: number; inTransitOrders: number; attentionRequired: number };

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

function statusLabel(status: string) {
  return {
    IDLE: "대기",
    TO_PICKUP: "픽업 이동",
    WAITING_LOAD: "상차 대기",
    IN_TRANSIT: "배송 중",
    WAITING_UNLOAD: "하차 대기",
    OUT_OF_SERVICE: "고장 격리",
  }[status] ?? status;
}

export default function ControlPage() {
  const [fleets, setFleets] = useState<Fleet[]>([]);
  const [selectedId, setSelectedId] = useState<string>();
  const [route, setRoute] = useState<Route>();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [stats, setStats] = useState<Stats>();
  const [message, setMessage] = useState("차량 상태를 불러오는 중...");
  const [busy, setBusy] = useState(false);

  const selected = useMemo(
    () => fleets.find((fleet) => fleet.fleetId === selectedId),
    [fleets, selectedId],
  );

  const loadOverview = useCallback(async () => {
    try {
      const response = await fetch(`${apiUrl}/control/overview`, { cache: "no-store" });
      if (!response.ok) throw new Error("overview fetch failed");
      const data = (await response.json()) as { fleets: Fleet[]; alerts: Alert[]; stats: Stats; routes: Route[] };
      setFleets(data.fleets);
      setAlerts(data.alerts);
      setStats(data.stats);
      setSelectedId((current) => current ?? data.fleets[0]?.fleetId);
      setRoute((current) => current ?? data.routes[0]);
      if (!data.fleets.length) setMessage("등록된 차량이 없습니다.");
    } catch {
      setMessage("API에 연결할 수 없습니다. 원격 관제 서버를 확인해 주세요.");
    }
  }, []);

  useEffect(() => {
    const initialTimer = window.setTimeout(() => void loadOverview(), 0);
    const timer = window.setInterval(() => void loadOverview(), 2_000);
    return () => {
      window.clearTimeout(initialTimer);
      window.clearInterval(timer);
    };
  }, [loadOverview]);

  async function postAction(path: string, success: string) {
    setBusy(true);
    try {
      const response = await fetch(`${apiUrl}${path}`, { method: "POST" });
      const data = (await response.json().catch(() => null)) as {
        detail?: string;
        fleet?: Fleet;
        route?: Route;
        replacementFleet?: Fleet | null;
        replacementRoute?: Route | null;
      } | null;
      if (!response.ok) throw new Error(data?.detail ?? "요청에 실패했습니다.");
      if (data?.fleet) {
        setFleets((current) => current.map((fleet) => fleet.fleetId === data.fleet?.fleetId ? data.fleet : fleet));
      }
      if (data?.route) setRoute(data.route);
      if (data?.replacementRoute) setRoute(data.replacementRoute);
      if (data?.replacementFleet) setFleets((current) => current.map((fleet) => fleet.fleetId === data.replacementFleet?.fleetId ? data.replacementFleet : fleet));
      setMessage(success);
      await loadOverview();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "요청에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  async function resetSeed() {
    setBusy(true);
    try {
      const response = await fetch(`${apiUrl}/control/seed-reset`, { method: "POST" });
      if (!response.ok) throw new Error("발표 상태 초기화에 실패했습니다.");
      setRoute(undefined);
      setMessage("발표용 샘플 상태로 초기화했습니다.");
      await loadOverview();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "초기화에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="control-page control-dashboard">
      <header className="topbar">
        <div><p className="eyebrow">FLEET CONTROL SIMULATOR</p><h1>차량 관제 시뮬레이터</h1></div>
        <Link className="back-link" href="/">관제센터로 돌아가기</Link>
      </header>
      <section className="control-intro control-toolbar">
        <div><p className="eyebrow">LIVE POLLING · 2 SEC</p><h2>실시간 자율주행 관제</h2><p>{message}</p></div>
        <div className="control-intro-actions"><Link className="market-link" href="/market">입찰 시장 보기</Link><button className="reset-button" disabled={busy} onClick={() => void resetSeed()} type="button">발표 상태 초기화</button></div>
      </section>
      {stats && <section className="control-stats" aria-label="관제 요약"><div><span>공개 경매</span><strong>{stats.openAuctions}</strong></div><div><span>운행 차량</span><strong>{stats.activeFleets}</strong></div><div><span>배송 중 주문</span><strong>{stats.inTransitOrders}</strong></div><div className={stats.attentionRequired ? "attention" : ""}><span>확인 필요</span><strong>{stats.attentionRequired}</strong></div></section>}
      <section className="control-workspace">
        <div className="fleet-column">
          <div className="workspace-title"><p className="eyebrow">AUTONOMOUS FLEET</p><h3>차량 현황</h3></div>
          <div className="fleet-grid">
          {fleets.map((fleet) => (
            <button className={`fleet-card ${selectedId === fleet.fleetId ? "selected" : ""}`} key={fleet.fleetId} onClick={() => setSelectedId(fleet.fleetId)} type="button">
              <div className="fleet-card-head"><span className={`status-dot ${fleet.status.toLowerCase()}`} /><strong>{fleet.name}</strong><small>{statusLabel(fleet.status)}</small></div>
              <p>{fleet.currentLoadKg.toLocaleString()} / {fleet.capacityKg.toLocaleString()}kg</p>
              <small>{fleet.location.coordinates[1].toFixed(4)}, {fleet.location.coordinates[0].toFixed(4)}</small>
            </button>
          ))}
          {!fleets.length && <div className="empty-market">차량 데이터가 아직 없어.</div>}
          </div>
        </div>
        <section className="panel control-map-panel"><div className="panel-title"><div><p className="eyebrow">GOOGLE MAPS · LIVE FLEET</p><h3>실시간 차량 위치와 경로</h3></div><span>2초마다 갱신</span></div><GoogleFleetMap fleets={fleets} stops={route?.stops.map((stop) => ({ label: stop.type === "PICKUP" ? "픽업" : "하차", location: stop.location }))} /></section>
        <div className="control-side">
          <article className="control-panel">
          {selected ? <>
            <p className="eyebrow">SELECTED FLEET</p>
            <h3>{selected.name}</h3>
            <div className="control-status"><span className={`status-dot ${selected.status.toLowerCase()}`} /> {statusLabel(selected.status)} <strong>{selected.currentLoadKg.toLocaleString()}kg</strong></div>
            <div className="control-actions">
              <button className="control-button" disabled={busy || selected.status === "OUT_OF_SERVICE"} onClick={() => void postAction(`/fleets/${selected.fleetId}/simulate-step`, "차량을 다음 경유지 방향으로 1스텝 이동했습니다.")} type="button">다음 위치로 이동</button>
              <button className="danger-button" disabled={busy || selected.status === "OUT_OF_SERVICE"} onClick={() => void postAction(`/fleets/${selected.fleetId}/breakdown`, "고장 처리 후 대체배차를 요청했습니다.")} type="button">고장 처리·대체배차</button>
            </div>
            {route && <div className="route-strip"><div><span className="eyebrow">ACTIVE ROUTE v{route.version}</span><strong>{route.status}</strong></div>{route.stops.map((stop) => <div className="route-stop" key={`${stop.orderId}-${stop.sequence}`}><small>{stop.sequence} · {stop.type}</small><span>{stop.status}</span></div>)}</div>}
          </> : <div className="empty-detail">왼쪽에서 차량을 선택해 주세요.</div>}
          </article>
          <section className="alert-panel"><div className="panel-title"><div><p className="eyebrow">OPERATIONS ALERTS</p><h3>장애·확인 알림</h3></div><span>{alerts.length ? `${alerts.length}건` : "정상"}</span></div>{alerts.length ? <div className="alert-list">{alerts.map((alert) => <div className={`alert-row ${alert.severity.toLowerCase()}`} key={alert.alertId}><span>{alert.severity}</span><div><strong>{alert.title}</strong><p>{alert.message}</p></div></div>)}</div> : <div className="empty-alert">현재 확인이 필요한 장애나 게이트가 없어.</div>}</section>
        </div>
      </section>
    </main>
  );
}
