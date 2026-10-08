"use client";

import Image from "next/image";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { Badge, Empty, Icon, Panel, Stats } from "@/components/Dashboard";
import { sampleApples } from "@/lib/sample-apples";
import { AutoAuctionDemo, useDemo } from "@/components/DemoProvider";
import { DEMO_AUCTION_MS } from "@/lib/auction-demo";
import { logisticsApiUrl, logisticsFetch, logisticsLive } from "@/lib/logistics-client";

type Lot = {
  cqcId: string;
  lotId: string;
  sellerId: string;
  variety: string;
  qualityGrade: string;
  quantityKg: number;
  reservePriceWon: number;
  auctionStatus: string;
  closesAt: string;
  createdAt: string;
};
type Bid = {
  bidId: string;
  buyerId: string;
  priceWon: number;
  placedAt: string;
};
const won = (value: number) => `${value.toLocaleString("ko-KR")}원`;
const grade = (value: string) =>
  ({ SPECIAL: "특", PREMIUM: "상", STANDARD: "보통" })[value] ?? value;
const variety = (value: string) =>
  ({ fuji: "부사", yanggwang: "양광" })[value.toLowerCase()] ?? value;
const time = (value: string) =>
  new Date(value).toLocaleTimeString("ko-KR", { hour12: false });
const buyerLabel = (value: string) => value.split("-FE-DEMO-")[0];
function photo(lot: Lot) {
  return sampleApples.find(
    (apple) =>
      apple.variety === variety(lot.variety) &&
      apple.grade === grade(lot.qualityGrade),
  );
}
function remaining(closesAt: string, now: number) {
  const seconds = Math.max(0, Math.floor((Date.parse(closesAt) - now) / 1000));
  return seconds
    ? `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`
    : "마감 시각 경과";
}

export default function MarketPage() {
  const { enabled: autoEnabled } = useDemo();
  const [role, setRole] = useState<"buyer" | "admin">("buyer");
  const [lots, setLots] = useState<Lot[]>([]);
  const [selectedId, setSelectedId] = useState<string>();
  const [bidData, setBidData] = useState<{ lotId: string; bids: Bid[] }>();
  const [buyerId, setBuyerId] = useState("buyer-demo");
  const [price, setPrice] = useState("");
  const [message, setMessage] = useState("");
  const [connected, setConnected] = useState(false);
  const [bidConnected, setBidConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(0);
  const [updatedAt, setUpdatedAt] = useState("");
  const [revision, setRevision] = useState(0);
  const [allBids, setAllBids] = useState(false);
  const selected = lots.find((lot) => lot.lotId === selectedId);
  const bids = bidData && bidData.lotId === selectedId ? bidData.bids : [];
  const highestBid = bids[0];
  const minimum = Math.max(
    selected?.reservePriceWon ?? 1,
    (highestBid?.priceWon ?? 0) + 1,
  );
  const bidPrice = price === "" ? minimum : Number(price);
  const selectedPhoto = selected && photo(selected);

  useEffect(() => {
    const controller = new AbortController();
    async function refresh() {
      try {
        const response = await logisticsFetch("/lots?auction_status=OPEN", {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!response.ok) throw new Error();
        const data = (await response.json()) as Lot[];
        setLots(data);
        setConnected(true);
        setUpdatedAt(new Date().toLocaleTimeString("ko-KR", { hour12: false }));
        setSelectedId((current) =>
          autoEnabled && data.some((lot) => lot.cqcId.startsWith("FE-DEMO-"))
            ? data.find((lot) => lot.cqcId.startsWith("FE-DEMO-"))?.lotId
            : data.some((lot) => lot.lotId === current) ? current : data[0]?.lotId,
        );
      } catch {
        if (!controller.signal.aborted) setConnected(false);
      }
    }
    void refresh();
    const timer = window.setInterval(refresh, 2000);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [revision, autoEnabled]);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    const controller = new AbortController();
    async function refreshBids() {
      try {
        const response = await logisticsFetch(`/lots/${selectedId}/bids`, {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!response.ok) throw new Error();
        const data = (await response.json()) as Bid[];
        setBidData({ lotId: selectedId!, bids: data });
        setBidConnected(true);
      } catch {
        if (!controller.signal.aborted) setBidConnected(false);
      }
    }
    void refreshBids();
    const timer = window.setInterval(refreshBids, 2000);
    // 가상 물류는 2초 조회만으로 갱신하고, 실제 물류 API에서만 경매 WebSocket을 연다.
    const socket = logisticsLive
      ? new WebSocket(`${logisticsApiUrl.replace(/^http/, "ws")}/ws/auctions/${selectedId}`)
      : null;
    if (socket)
      socket.onmessage = () => {
        void refreshBids();
        setRevision((value) => value + 1);
      };
    return () => {
      controller.abort();
      clearInterval(timer);
      socket?.close();
    };
  }, [selectedId]);

  const selectLot = useCallback((lot: Lot) => {
    setSelectedId(lot.lotId);
    setPrice("");
    setBidConnected(false);
    setMessage("");
  }, []);

  async function submitBid(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || !connected || !bidConnected || role !== "buyer") return;
    setBusy(true);
    try {
      const response = await logisticsFetch(`/lots/${selected.lotId}/bids`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          buyerId: buyerId.trim(),
          priceWon: bidPrice,
          destination: { type: "Point", coordinates: [127.028, 37.498] },
        }),
      });
      const result = await response.json();
      if (!response.ok)
        throw new Error(
          typeof result.detail === "string"
            ? result.detail
            : "입찰에 실패했습니다.",
        );
      setBidData((current) => ({
        lotId: selected.lotId,
        bids: [
          result as Bid,
          ...(current?.lotId === selected.lotId
            ? current.bids.filter((bid) => bid.bidId !== result.bidId)
            : []),
        ].sort((a, b) => b.priceWon - a.priceWon),
      }));
      setPrice("");
      setMessage("입찰이 접수됐습니다.");
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "서버에 연결할 수 없습니다.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function closeAuction() {
    if (!selected || role !== "admin" || !connected) return;
    setBusy(true);
    try {
      const response = await logisticsFetch(`/lots/${selected.lotId}/close`, {
        method: "POST",
      });
      if (!response.ok) throw new Error("경매 마감에 실패했습니다.");
      const result = (await response.json()) as { winningBid?: Bid };
      setMessage(
        result.winningBid
          ? `${result.winningBid.buyerId} 낙찰로 경매를 마감했습니다. 결제 완료(가상) · 실결제 없음 · 배차 대기`
          : "입찰 없이 경매를 마감했습니다.",
      );
      setPrice("");
      setRevision((value) => value + 1);
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "서버에 연결할 수 없습니다.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="dashboard market-page">
      <AutoAuctionDemo />
      <Stats
        items={[
          {
            label: "공개 경매",
            value: connected ? `${lots.length}건` : "—",
            icon: "market",
          },
          {
            label: "선택 출품 입찰",
            value: bidConnected ? `${bids.length}건` : "—",
            icon: "document",
          },
          {
            label: "선택 출품 물량",
            value: selected ? `${selected.quantityKg.toLocaleString()}kg` : "—",
            icon: "box",
          },
          {
            label: "현재 최고 입찰가",
            value: highestBid ? won(highestBid.priceWon) : "—",
            icon: "market",
          },
        ]}
      />
      <section className="page-toolbar">
        <h1>
          <Icon name="market" /> B2B 사과 입찰 시장
        </h1>
        <Badge tone={connected ? "success" : "warning"}>
          {connected ? (logisticsLive ? "● 서버 연결됨" : "● 시연용 가상 물류") : "서버 연결 대기"}
        </Badge>
        <span className="muted toolbar-update">
          최종 업데이트 {updatedAt || "—"}
        </span>
        <div className="role-switch" aria-label="시뮬레이션 역할 전환">
          <button
            type="button"
            className={role === "buyer" ? "active" : ""}
            onClick={() => setRole("buyer")}
            aria-pressed={role === "buyer"}
          >
            구매자 모드
          </button>
          <button
            type="button"
            className={role === "admin" ? "active" : ""}
            onClick={() => setRole("admin")}
            aria-pressed={role === "admin"}
          >
            관리자 모드
          </button>
        </div>
      </section>
      {!connected && (
        <div className="page-notice">
          <Badge tone="warning">연결 대기</Badge>입찰 서버에 연결할 수 없습니다.
          자동으로 다시 연결합니다.
        </div>
      )}
      {message && (
        <div className="page-notice" role="status">
          {message}
        </div>
      )}
      <div className="market-workspace">
        <Panel
          title="공개 출품 목록"
          icon="camera"
          action={<small>총 {lots.length}건</small>}
        >
          <div className="lot-list">
            {lots.map((lot) => (
              <button
                className={`lot-card ${selectedId === lot.lotId ? "selected" : ""}`}
                key={lot.lotId}
                onClick={() => selectLot(lot)}
                type="button"
                aria-pressed={selectedId === lot.lotId}
                disabled={busy}
              >
                {photo(lot) ? (
                  <Image
                    src={photo(lot)!.images[0]}
                    alt={`${variety(lot.variety)} 참고 이미지`}
                    width={160}
                    height={160}
                  />
                ) : (
                  <span className="photo-placeholder">
                    <Icon name="apple" />
                  </span>
                )}
                <div>
                  <div className="lot-card-title">
                    <strong>{lot.lotId}</strong>
                    <Badge tone="success">진행 중</Badge>
                  </div>
                  <p>
                    {variety(lot.variety)}{" "}
                    <Badge tone="purple">{grade(lot.qualityGrade)}</Badge>{" "}
                    <span>{lot.quantityKg.toLocaleString()}kg</span>
                  </p>
                  <p>
                    최저가 <b className="price">{won(lot.reservePriceWon)}</b>
                  </p>
                  <small>
                    <Icon name="clock" />{" "}
                    {lot.cqcId.startsWith("FE-DEMO-") ? `시연 구매자 자동 입찰 · ${DEMO_AUCTION_MS / 1000}초 마감` : now ? remaining(lot.closesAt, now) : "—"}
                  </small>
                </div>
                <span className="chevron">›</span>
              </button>
            ))}
          </div>
          {!lots.length && (
            <Empty>
              {connected
                ? "진행 중인 공개 경매가 없습니다."
                : "출품 데이터를 기다리고 있습니다."}
            </Empty>
          )}
        </Panel>
        <Panel
          title="선택 출품 상세"
          icon="apple"
          action={<small>{selected?.lotId}</small>}
        >
          {selected ? (
            <>
              <div className="lot-detail-top">
                {selectedPhoto ? (
                  <div className="apple-gallery">
                    <Image
                      className="apple-main"
                      src={selectedPhoto.images[0]}
                      alt="동일 품종·등급의 참고 사과"
                      width={640}
                      height={640}
                    />
                    <div className="apple-thumbs">
                      {selectedPhoto.images.slice(1).map((src) => (
                        <Image
                          key={src}
                          src={src}
                          alt="참고 사과의 다른 촬영 각도"
                          width={240}
                          height={240}
                        />
                      ))}
                    </div>
                  </div>
                ) : (
                  <Empty>출품 사진이 아직 등록되지 않았습니다.</Empty>
                )}
                <dl className="detail-table">
                  <dt>품종</dt>
                  <dd>{variety(selected.variety)}</dd>
                  <dt>등급</dt>
                  <dd>
                    <Badge tone="purple">{grade(selected.qualityGrade)}</Badge>
                  </dd>
                  <dt>수량</dt>
                  <dd>{selected.quantityKg.toLocaleString()}kg</dd>
                  <dt>출품자</dt>
                  <dd>{selected.sellerId}</dd>
                  <dt>최저 낙찰가</dt>
                  <dd>{won(selected.reservePriceWon)}</dd>
                  <dt>마감</dt>
                  <dd className="price">{time(selected.closesAt)}</dd>
                </dl>
              </div>
              <p className="footnote muted">
                사진은 같은 품종·등급의 참고 이미지이며 해당 출품의 실물 사진이
                아닙니다.
              </p>
              <div className="history-strip">
                <h3>출품 진행 이력</h3>
                <div>
                  <span>
                    <Icon name="check" />
                    <b>CQC 결과 등록</b>
                  </span>
                  <Icon name="arrow" />
                  <span>
                    <Icon name="check" />
                    <b>출품 등록</b>
                    <small>{time(selected.createdAt)}</small>
                  </span>
                  <Icon name="arrow" />
                  <span>
                    <Icon name="market" />
                    <b>경매 진행 중</b>
                  </span>
                </div>
              </div>
            </>
          ) : (
            <Empty>왼쪽에서 출품을 선택해 주세요.</Empty>
          )}
        </Panel>
        <div className="market-side">
          <Panel
            title="실시간 입찰 현황"
            icon="market"
            action={
              <Badge tone={bidConnected ? "success" : "neutral"}>
                {bidConnected ? "● 업데이트 중" : "대기"}
              </Badge>
            }
          >
            <div className="bid-summary">
              <div>
                <small>현재 최고가</small>
                <strong>
                  {highestBid ? won(highestBid.priceWon) : "입찰 대기"}
                </strong>
              </div>
              <div>
                <small>최고가 입찰자</small>
                <b>{highestBid ? buyerLabel(highestBid.buyerId) : "—"}</b>
              </div>
              <div>
                <small>총 입찰 수</small>
                <b>{bids.length}건</b>
              </div>
            </div>
            <table>
              <thead>
                <tr>
                  <th>순위</th>
                  <th>입찰자</th>
                  <th>입찰 금액(원)</th>
                  <th>입찰 시간</th>
                </tr>
              </thead>
              <tbody>
                {bids.slice(0, 5).map((bid, index) => (
                  <tr
                    key={bid.bidId}
                    className={index === 0 ? "leading-bid" : ""}
                  >
                    <td>{index + 1}</td>
                    <td title={bid.buyerId}>{buyerLabel(bid.buyerId)}</td>
                    <td>{bid.priceWon.toLocaleString()}</td>
                    <td>{time(bid.placedAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!bids.length && <Empty>첫 입찰을 기다리고 있습니다.</Empty>}
          </Panel>
          <Panel title="입찰 제출" icon="document">
            <form onSubmit={submitBid} className="bid-form">
              <label htmlFor="buyer">구매자 ID</label>
              <input
                id="buyer"
                value={buyerId}
                onChange={(event) => setBuyerId(event.target.value)}
                required
                maxLength={100}
                disabled={role === "admin" || busy}
              />
              <label htmlFor="bid-price">입찰 금액</label>
              <div className="input-unit">
                <input
                  id="bid-price"
                  type="number"
                  min={minimum}
                  step={1}
                  value={bidPrice}
                  onChange={(event) => setPrice(event.target.value)}
                  required
                  disabled={role === "admin" || busy}
                />
                <span>원</span>
              </div>
              <button
                className="primary-button"
                disabled={
                  busy ||
                  !selected ||
                  !connected ||
                  !bidConnected ||
                  role !== "buyer" ||
                  !buyerId.trim()
                }
                type="submit"
              >
                <Icon name="arrow" />
                {busy ? "처리 중…" : "입찰 제출"}
              </button>
            </form>
            <p className="footnote muted">
              현재 최고가보다 높은 금액을 입력해 주세요.
            </p>
            <div className="notice-box">
              시뮬레이션에서는 실제 결제가 발생하지 않습니다.
            </div>
          </Panel>
        </div>
      </div>
      <div className="market-bottom">
        <Panel
          title="최근 입찰 이벤트"
          icon="clock"
          action={
            <button
              className="text-button"
              type="button"
              onClick={() => setAllBids(!allBids)}
            >
              {allBids ? "접기" : "전체 보기"} ›
            </button>
          }
        >
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>시간</th>
                  <th>이벤트 유형</th>
                  <th>LOT 번호</th>
                  <th>내용</th>
                  <th>관련 정보</th>
                </tr>
              </thead>
              <tbody>
                {[...bids]
                  .sort(
                    (a, b) => Date.parse(b.placedAt) - Date.parse(a.placedAt),
                  )
                  .slice(0, allBids ? undefined : 4)
                  .map((bid) => (
                    <tr key={bid.bidId}>
                      <td>{time(bid.placedAt)}</td>
                      <td>
                        <Badge
                          tone={
                            bid.bidId === highestBid?.bidId
                              ? "success"
                              : "neutral"
                          }
                        >
                          {bid.bidId === highestBid?.bidId
                            ? "최고가 입찰"
                            : "입찰 접수"}
                        </Badge>
                      </td>
                      <td>{selectedId}</td>
                      <td>{buyerLabel(bid.buyerId)} 입찰이 접수됐습니다.</td>
                      <td>{won(bid.priceWon)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          {!bids.length && <Empty>선택한 출품의 입찰 이벤트가 없습니다.</Empty>}
        </Panel>
        <Panel
          title="최고가 낙찰 · 경매 마감"
          icon="check"
          className="auction-close"
          action={<Badge tone="rose">관리자 모드 전용</Badge>}
        >
          <p>선택한 출품의 최고가 입찰을 확정하고 경매를 마감합니다.</p>
          <button
            className="outline-button"
            type="button"
            disabled={role !== "admin" || !selected || busy || !connected}
            onClick={() => void closeAuction()}
          >
            {busy ? "처리 중…" : "낙찰 처리하기"}
          </button>
          <div className="notice-box">
            {role === "buyer"
              ? "현재 구매자 모드입니다. 관리자 모드에서 마감할 수 있습니다."
              : "시연용 관리자 화면입니다. 마감 후 되돌릴 수 없습니다."}
          </div>
        </Panel>
      </div>
    </main>
  );
}
