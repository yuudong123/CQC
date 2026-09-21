"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

type Role = "buyer" | "admin";
type Lot = { lotId: string; crop: string; variety: string; qualityGrade: string; quantityKg: number; reservePriceWon: number; suggestedPriceWon: number | null; auctionStatus: string; closesAt: string };
type Bid = { bidId: string; buyerId: string; priceWon: number; placedAt: string };
type BidEvent = { type: string; bid?: Bid };

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const won = (value: number) => `${value.toLocaleString("ko-KR")}원`;

export default function MarketPage() {
  const [role, setRole] = useState<Role>("buyer");
  const [lots, setLots] = useState<Lot[]>([]);
  const [selectedId, setSelectedId] = useState<string>();
  const [bids, setBids] = useState<Bid[]>([]);
  const [buyerId, setBuyerId] = useState("buyer-demo");
  const [price, setPrice] = useState(0);
  const [status, setStatus] = useState("공개 경매를 불러오는 중...");
  const [busy, setBusy] = useState(false);

  const selected = useMemo(() => lots.find((lot) => lot.lotId === selectedId), [lots, selectedId]);
  const highestBid = bids[0];
  const bidPrice = price || Math.max(selected?.reservePriceWon ?? 0, (highestBid?.priceWon ?? 0) + 10_000);

  const loadLots = useCallback(async () => {
    const response = await fetch(`${apiUrl}/lots?auction_status=OPEN`, { cache: "no-store" });
    if (!response.ok) throw new Error("market fetch failed");
    const data = (await response.json()) as Lot[];
    setLots(data);
    setSelectedId((current) => data.some((lot) => lot.lotId === current) ? current : data[0]?.lotId);
    setStatus(data.length ? "진행 중인 경매" : "진행 중인 공개 경매가 없습니다.");
  }, []);

  const loadBids = useCallback(async (lotId: string) => {
    const response = await fetch(`${apiUrl}/lots/${lotId}/bids`, { cache: "no-store" });
    if (response.ok) setBids((await response.json()) as Bid[]);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadLots().catch(() => setStatus("API에 연결할 수 없습니다. 관제 서버 상태를 확인해 주세요."));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadLots]);

  useEffect(() => {
    if (!selectedId) return;
    const timer = window.setTimeout(() => void loadBids(selectedId), 0);
    const socket = new WebSocket(`${apiUrl.replace(/^http/, "ws")}/ws/auctions/${selectedId}`);
    socket.onmessage = (event) => {
      const message = JSON.parse(event.data) as BidEvent;
      if (message.type === "BID_PLACED" && message.bid) {
        setBids((current) => [message.bid as Bid, ...current]);
        setPrice(message.bid.priceWon + 10_000);
      }
      if (message.type === "AUCTION_CLOSED") void loadLots();
    };
    return () => { window.clearTimeout(timer); socket.close(); };
  }, [loadBids, loadLots, selectedId]);

  async function submitBid(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true);
    const response = await fetch(`${apiUrl}/lots/${selected.lotId}/bids`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ buyerId, priceWon: bidPrice, destination: { type: "Point", coordinates: [127.028, 37.498] } }),
    });
    if (response.ok) setStatus("입찰이 접수됐습니다.");
    else {
      const error = (await response.json().catch(() => null)) as { detail?: string } | null;
      setStatus(error?.detail ?? "입찰에 실패했습니다.");
    }
    setBusy(false);
  }

  async function closeAuction() {
    if (!selected) return;
    setBusy(true);
    const response = await fetch(`${apiUrl}/lots/${selected.lotId}/close`, { method: "POST" });
    if (response.ok) {
      const result = (await response.json()) as { winningBid?: Bid | null };
      setStatus(result.winningBid ? `${result.winningBid.buyerId} 낙찰로 경매를 마감했습니다.` : "입찰 없이 경매를 마감했습니다.");
      await loadLots();
    } else setStatus("경매 마감에 실패했습니다.");
    setBusy(false);
  }

  function selectLot(lot: Lot) { setSelectedId(lot.lotId); setPrice(lot.reservePriceWon + 10_000); }

  return (
    <main className={`market-page ${role === "admin" ? "admin-market" : ""}`}>
      <header className="topbar market-topbar">
        <div><p className="eyebrow">B2B CROP MARKET</p><h1>{role === "buyer" ? "농산물 입찰 시장" : "경매 운영 관리"}</h1></div>
        <div className="market-header-actions">
          <div className="role-switch" aria-label="데모 화면 전환">
            <button className={role === "buyer" ? "active" : ""} onClick={() => setRole("buyer")} type="button">입찰자</button>
            <button className={role === "admin" ? "active" : ""} onClick={() => setRole("admin")} type="button">관리자</button>
          </div>
          <Link className="back-link" href="/">홈</Link>
        </div>
      </header>
      <section className="market-intro">
        <div><p className="eyebrow">{role === "buyer" ? "BUYER · LIVE AUCTION" : "ADMIN · AUCTION DESK"}</p><h2>{role === "buyer" ? <>검증된 사과를<br />실시간으로 입찰하세요.</> : <>입찰 흐름을 보고<br />낙찰을 확정하세요.</>}</h2><p>{status}</p></div>
        <div className="live-chip"><span /> 실시간 경매 연결</div>
      </section>
      {role === "admin" && <section className="auction-summary" aria-label="경매 운영 요약"><div><span>진행 중</span><strong>{lots.length}</strong></div><div><span>선택 경매 입찰</span><strong>{bids.length}</strong></div><div><span>현재 최고가</span><strong>{highestBid ? won(highestBid.priceWon) : "대기"}</strong></div></section>}
      <section className="market-grid">
        <div className="lot-list">
          {lots.map((lot) => <button className={`lot-card ${selectedId === lot.lotId ? "selected" : ""}`} key={lot.lotId} onClick={() => selectLot(lot)} type="button"><span className="lot-status">OPEN</span><strong>{lot.variety} · {lot.qualityGrade}</strong><p>{lot.crop} · {lot.quantityKg.toLocaleString()}kg</p><small>{role === "buyer" ? "최저 낙찰가" : "설정 하한가"} {won(lot.reservePriceWon)}</small></button>)}
          {!lots.length && <div className="empty-market">현재 공개된 경매가 없어. 발표 상태 초기화 후 다시 확인해줘.</div>}
        </div>
        <article className="bid-panel">
          {selected ? role === "buyer" ? <>
            <p className="eyebrow">SELECTED LOT</p><h3>{selected.variety} · {selected.qualityGrade}</h3><p className="lot-detail">{selected.quantityKg.toLocaleString()}kg · 최저 낙찰가 {won(selected.reservePriceWon)}</p>
            <div className="latest-bid">현재 최고 입찰<strong>{highestBid ? `${highestBid.buyerId} · ${won(highestBid.priceWon)}` : "첫 입찰을 기다리는 중"}</strong></div>
            <form onSubmit={submitBid}><label>구매자 ID<input value={buyerId} onChange={(event) => setBuyerId(event.target.value)} required /></label><label>입찰 금액(원)<input type="number" min={selected.reservePriceWon} step={10000} value={bidPrice} onChange={(event) => setPrice(Number(event.target.value))} required /></label><button className="bid-button" disabled={busy} type="submit">{won(bidPrice)} 입찰하기</button></form>
          </> : <>
            <p className="eyebrow">AUCTION CONTROL</p><h3>{selected.variety} · {selected.qualityGrade}</h3>
            <div className="admin-lot-meta"><span>출품량<strong>{selected.quantityKg.toLocaleString()}kg</strong></span><span>하한가<strong>{won(selected.reservePriceWon)}</strong></span></div>
            <div className="admin-bid-list"><div className="admin-bid-head"><strong>실시간 입찰 현황</strong><span>{bids.length}건</span></div>{bids.slice(0, 4).map((bid, index) => <div className="admin-bid-row" key={bid.bidId}><span>{index + 1}</span><strong>{bid.buyerId}</strong><b>{won(bid.priceWon)}</b></div>)}{!bids.length && <p className="admin-empty">아직 접수된 입찰이 없습니다.</p>}</div>
            <button className="close-auction-button" disabled={busy} onClick={() => void closeAuction()} type="button">최고가 낙찰 · 경매 마감</button><p className="admin-note">마감 즉시 주문 생성과 자동배차가 이어집니다.</p>
          </> : <div className="empty-detail">왼쪽 경매를 선택해 주세요.</div>}
        </article>
      </section>
    </main>
  );
}
