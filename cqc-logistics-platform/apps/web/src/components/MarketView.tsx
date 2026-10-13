"use client";

import Image from "next/image";
import Link from "next/link";
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
type Order = { orderId: string; lotId: string; buyerId: string; priceWon: number; status: string };
const ORDER_STATUS: Record<string, string> = {
  MATCHED: "낙찰 · 배차 대기",
  DISPATCHING: "배차 중",
  ASSIGNED: "차량 배정",
  DELIVERED: "배송 완료",
  CANCELLED: "취소",
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

// 관리자(농가 판매 관리)와 구매자 화면을 주소로 나눈다. 같은 출품·입찰 데이터를 각자 역할에 맞게 보여 준다.
export default function MarketView({ role }: { role: "buyer" | "admin" }) {
  const { enabled: autoEnabled } = useDemo();
  const [bizOpen, setBizOpen] = useState(false);
  const [orders, setOrders] = useState<Order[]>([]);
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
        if (role === "admin") {
          const overview = await logisticsFetch("/control/overview", { cache: "no-store", signal: controller.signal });
          if (overview.ok) setOrders(((await overview.json()) as { orders: Order[] }).orders);
        }
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
  }, [revision, autoEnabled, role]);

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

  return (
    <main className={`dashboard market-page ${role}`}>
      {role === "buyer" && (
        <header className="buyer-header">
          <div className="brand">
            <Icon name="apple" />
            <div>
              <strong>CQC 사과 시장</strong>
            </div>
          </div>
          <span className="buyer-user">시연 마트 · 구매자</span>
          <Link href="/market" className="buyer-switch">관리자 화면으로 →</Link>
        </header>
      )}
      {/* 자동 시연(출품 → 입찰 → 낙찰 → 결제)은 낙찰자 결제가 구매자 쪽에서 일어나므로 구매자 화면에서 돌린다. */}
      {role === "buyer" && <AutoAuctionDemo />}
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
          <Icon name="market" /> {role === "admin" ? "입찰 시장 관리" : "B2B 사과 입찰 시장"}
        </h1>
        <Badge tone={connected ? "success" : "warning"}>
          {connected ? (logisticsLive ? "● 서버 연결됨" : "● 시연용 가상 물류") : "서버 연결 대기"}
        </Badge>
        <span className="muted toolbar-update">
          최종 업데이트 {updatedAt || "—"}
        </span>
        {role === "admin" && (
          <div className="market-admin-actions">
            <Badge tone="warning">사업자 미등록 · PG 미연결</Badge>
            <button type="button" className="outline-button" onClick={() => setBizOpen(true)}>
              판매자(사업자) 등록
            </button>
            <Link href="/market/buyer" className="primary-button buyer-link">
              구매자 화면 열기 →
            </Link>
          </div>
        )}
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
          {role === "buyer" ? (
            <>
              <Panel title="입찰 제출" icon="document">
                <form onSubmit={submitBid} className="bid-form">
                  <label htmlFor="buyer">구매자 ID</label>
                  <input
                    id="buyer"
                    value={buyerId}
                    onChange={(event) => setBuyerId(event.target.value)}
                    required
                    maxLength={100}
                    disabled={busy}
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
                      disabled={busy}
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
            </>
          ) : (
            <>
            <Panel title="경매 결과" icon="check" className="auction-result">
              {selected ? (
                <div className="auction-rule">
                  <p>
                    마감{" "}
                    <b>
                      {selected.cqcId.startsWith("FE-DEMO-")
                        ? `시연 ${DEMO_AUCTION_MS / 1000}초 경매`
                        : `${time(selected.closesAt)} · ${now ? remaining(selected.closesAt, now) : "—"}`}
                    </b>
                  </p>
                  <p className={highestBid && highestBid.priceWon >= selected.reservePriceWon ? "expected" : "muted"}>
                    {highestBid && highestBid.priceWon >= selected.reservePriceWon
                      ? `지금 마감되면 ${buyerLabel(highestBid.buyerId)} ${won(highestBid.priceWon)} 낙찰`
                      : `최저가 ${won(selected.reservePriceWon)} 이상 입찰이 없으면 유찰`}
                  </p>
                </div>
              ) : (
                <Empty>왼쪽에서 출품을 선택하면 마감 정보가 보입니다.</Empty>
              )}
              <h3 className="result-head">최근 낙찰</h3>
              {orders.length ? (
                <table>
                  <thead>
                    <tr>
                      <th>출품</th>
                      <th>낙찰자</th>
                      <th>낙찰가</th>
                      <th>상태</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders.slice(-4).reverse().map((order) => (
                      <tr key={order.orderId}>
                        <td>{order.lotId}</td>
                        <td>{buyerLabel(order.buyerId)}</td>
                        <td>{won(order.priceWon)}</td>
                        <td>{ORDER_STATUS[order.status] ?? order.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <Empty>아직 낙찰된 출품이 없습니다.</Empty>
              )}
              <div className="notice-box">
                경매는 마감 시각에 최고가 입찰로 자동 낙찰됩니다. 판매자는 입찰 현황과 결과만 확인하고 직접 마감하지 않습니다.
              </div>
            </Panel>
            </>
          )}
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
      </div>
      {bizOpen && <BusinessModal onClose={() => setBizOpen(false)} />}
    </main>
  );
}

/** 판매자(사업자) 등록 화면. 실제 서비스에서 PG 결제를 받으려면 필요한 절차를 보여 주기만 하고 저장하지 않는다. */
function BusinessModal({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="biz-backdrop" onClick={onClose}>
      <div className="biz-modal" role="dialog" aria-modal="true" aria-labelledby="biz-title" onClick={(event) => event.stopPropagation()}>
        <div className="biz-head">
          <h2 id="biz-title">판매자(사업자) 등록</h2>
          <button type="button" className="text-button" onClick={onClose} aria-label="닫기">✕</button>
        </div>
        <p className="biz-lead">
          입찰 대금을 PG로 받으려면 농장의 사업자 등록과 PG 가맹 심사가 필요합니다.
        </p>
        <form className="biz-form" onSubmit={(event) => event.preventDefault()}>
          <label>상호(농장명)<input defaultValue="CQC 사과농장" /></label>
          <label>사업자등록번호<input placeholder="000-00-00000" inputMode="numeric" /></label>
          <label>대표자<input placeholder="대표자 이름" /></label>
          <label>사업장 주소<input placeholder="농장 주소" /></label>
          <label>통신판매업 신고번호<input placeholder="선택 입력" /></label>
          <label>정산 계좌<input placeholder="은행 · 계좌번호 · 예금주" /></label>
        </form>
        <ol className="biz-steps">
          <li><b>1</b>사업자 정보 입력</li>
          <li><b>2</b>서류 확인(사업자등록증·통장 사본)</li>
          <li><b>3</b>PG 가맹 심사</li>
          <li><b>4</b>결제 연동 완료</li>
        </ol>
        <div className="biz-foot">
          <span>PG 가맹 상태 <Badge tone="warning">미연결</Badge> · 시연에서는 저장하지 않습니다.</span>
          <button type="button" className="primary-button" disabled>등록 신청</button>
          <button type="button" className="outline-button" onClick={onClose}>닫기</button>
        </div>
      </div>
    </div>
  );
}
