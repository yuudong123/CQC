"use client";

import Image from "next/image";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { Badge, Icon, Panel } from "./Dashboard";
import { sampleApples } from "@/lib/sample-apples";

/**
 * 통합 흐름 시연 전용 페이지(/tour). 실제 API를 부르지 않고, 최종 화면 모양만 따라 그린 각본이다.
 * 농가(관리자)와 구매자 화면을 나눠 촬영 → 판정 → 선별 → 출품 → 입찰 → 낙찰 → 결제 → 배차를 한 흐름으로 보여 준다.
 * 화면은 밝은 실제 화면 그대로 두고, 누르거나 볼 곳에 노란 테두리만 순서대로 띄운다(녹화는 Win+G로 한다).
 * 자막은 화면 아래 띠에만 나오고, 시연 화면은 그 띠를 뺀 공간에 맞춰 줄어들어 서로 겹치지 않는다.
 * 넘기기: 노란 테두리를 클릭하거나 → · Space · Enter, 이전 단계는 ←.
 */

type Role = "farm" | "buyer";
type Screen = "console" | "market-farm" | "login" | "market-buyer" | "pay" | "dispatch" | "summary";
type View = {
  apple: "idle" | "shoot" | "judged";
  review: boolean;
  total: number;
  reinspection: number;
  errors: number;
  bin02: number;
  recentBin: string;
  lotListed: boolean;
  loginDone: boolean;
  lotOpen: boolean;
  bidPlaced: boolean;
  rivals: number;
  won: boolean;
  paid: boolean;
  dispatched: boolean;
};
type Step = {
  role: Role;
  screen: Screen;
  stage: number;
  target?: string;
  hint?: string;
  click?: boolean;
  caption: string;
  set?: Partial<View>;
};

const START: View = {
  apple: "idle", review: false, total: 5352, reinspection: 558, errors: 4, bin02: 379, recentBin: "",
  lotListed: false, loginDone: false, lotOpen: false, bidPlaced: false, rivals: 0, won: false, paid: false, dispatched: false,
};
// 자막은 발표자가 설명하는 말투로 쓴다. 한 단계에 한두 문장.
const STEPS: Step[] = [
  { role: "farm", screen: "console", stage: 0, target: "lights", hint: "설비 상태",
    caption: "먼저 농가가 보는 품질 관제 화면입니다. 위쪽 점 네 개가 모두 초록이면 촬영 장치와 판정 서버가 정상이라는 뜻입니다." },
  { role: "farm", screen: "console", stage: 0, target: "jobs", hint: "촬영 장치", set: { apple: "shoot" },
    caption: "사과가 라인에 들어오면 촬영 장치가 사과 한 개를 열두 각도에서 찍습니다." },
  { role: "farm", screen: "console", stage: 1, target: "result", hint: "AI 판정", set: { apple: "judged", total: 5353 },
    caption: "AI가 열두 장을 함께 보고 부사, 특 등급으로 판정했습니다. 신뢰도가 기준을 넘었으니 바로 선별로 넘어갑니다." },
  { role: "farm", screen: "console", stage: 2, target: "bin-02", hint: "2번 선별함", set: { bin02: 380, recentBin: "02" },
    caption: "가상 당도가 14 이상이라 부사 특, 당도 높음 칸인 2번 선별함으로 보냅니다. 방금 들어간 칸이 깜빡입니다." },
  { role: "farm", screen: "console", stage: 2, target: "exception", hint: "재검사함", set: { review: true, total: 5354, reinspection: 559, recentBin: "re" },
    caption: "신뢰도가 낮은 사과는 판정하지 않고 재검사함으로 보냅니다. 사람이 다시 볼 사과만 따로 모입니다." },
  { role: "farm", screen: "console", stage: 2, target: "kpis", hint: "오늘 숫자",
    caption: "위쪽 큰 숫자 세 개가 오늘 검사 수, 재검사율, 오류율입니다. 농가는 이 숫자로 오늘 라인 상태를 한눈에 확인합니다." },
  { role: "farm", screen: "market-farm", stage: 3, target: "list-btn", hint: "여기를 누릅니다", click: true,
    caption: "이제 입찰 시장으로 가 보겠습니다. 2번 선별함에 같은 등급 사과가 모여서, 농가는 이 묶음을 바로 출품할 수 있습니다." },
  { role: "farm", screen: "market-farm", stage: 3, target: "lot-farm", hint: "출품 완료", set: { lotListed: true, lotOpen: true },
    caption: "출품하면 품질 판정 결과가 출품 정보에 그대로 붙고 경매가 열립니다. 여기서부터는 구매자 차례입니다." },
  { role: "buyer", screen: "login", stage: 4, target: "login-btn", hint: "구매자 로그인", click: true,
    caption: "구매자는 자기 계정으로 따로 로그인합니다. 농가와 구매자는 서로 다른 화면을 씁니다." },
  { role: "buyer", screen: "market-buyer", stage: 4, target: "lot-buyer", hint: "열린 출품", set: { loginDone: true },
    caption: "구매자 화면에는 지금 경매 중인 출품만 보입니다. 사과 사진과 품종, 등급, 판정 신뢰도를 보고 고를 수 있습니다." },
  { role: "buyer", screen: "market-buyer", stage: 4, target: "bid-btn", hint: "입찰하기", click: true,
    caption: "희망 가격 6,500원을 넣고 입찰하겠습니다." },
  { role: "buyer", screen: "market-buyer", stage: 4, target: "bids", hint: "실시간 입찰", set: { bidPlaced: true, rivals: 2 },
    caption: "다른 구매자들의 입찰도 실시간으로 들어옵니다. 경매 시간이 끝나면 가장 높은 가격이 낙찰됩니다." },
  { role: "buyer", screen: "market-buyer", stage: 5, target: "won", hint: "낙찰", set: { won: true, lotOpen: false },
    caption: "경매가 끝났고, 시연 마트가 6,500원으로 낙찰받았습니다." },
  { role: "buyer", screen: "pay", stage: 6, target: "pay-btn", hint: "결제하기", click: true,
    caption: "낙찰자는 결제 화면으로 넘어와 결제합니다. 시연에서는 테스트 결제라 실제 돈은 나가지 않습니다." },
  { role: "buyer", screen: "pay", stage: 6, target: "pay-done", hint: "결제 완료", set: { paid: true },
    caption: "결제가 끝나야 주문이 확정되고, 농가 쪽으로 배차 요청이 넘어갑니다." },
  { role: "farm", screen: "dispatch", stage: 7, target: "dispatch-btn", hint: "배차하기", click: true,
    caption: "다시 농가 관리자 화면입니다. 결제된 주문이 배차 대기로 올라와 있어서 배차를 누릅니다." },
  { role: "farm", screen: "dispatch", stage: 7, target: "route", hint: "차량 배정", set: { dispatched: true },
    caption: "가장 가까운 차량이 배정되고, 사과는 농가에서 구매자에게 출발합니다." },
  { role: "farm", screen: "summary", stage: 7, target: "summary", hint: "전체 흐름",
    caption: "사과 한 개가 촬영부터 판정, 선별, 출품, 낙찰, 결제, 배차까지 하나의 흐름으로 이어졌습니다. 이상으로 통합 흐름 시연을 마치겠습니다." },
];
const viewAt = (index: number) => STEPS.slice(0, index + 1).reduce<View>((view, step) => ({ ...view, ...step.set }), START);
const STAGE_W = 1600;
const STAGE_H = 900;
const CAPTION_H = 96;

const MAIN = sampleApples[2];
const REVIEW = sampleApples[0];

export default function TourDemo() {
  const [index, setIndex] = useState(0);
  const [pressing, setPressing] = useState(false);
  const [scale, setScale] = useState(1);
  const [spot, setSpot] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const step = STEPS[index];
  const view = viewAt(index);

  const go = useCallback((next: number) => {
    setPressing(false);
    setIndex(Math.max(0, Math.min(STEPS.length - 1, next)));
  }, []);
  // 누르는 단계는 눌림 효과를 잠깐 보여 준 뒤 넘어간다.
  const advance = useCallback(() => {
    if (index >= STEPS.length - 1) return;
    if (STEPS[index].click) {
      setPressing(true);
      window.setTimeout(() => go(index + 1), 450);
    } else go(index + 1);
  }, [index, go]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "ArrowRight" || event.key === " " || event.key === "Enter") { event.preventDefault(); advance(); }
      else if (event.key === "ArrowLeft") go(index - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [advance, go, index]);

  // 시연 화면(1600×900)을 자막 띠를 뺀 공간에 맞춰 줄인다.
  useEffect(() => {
    const fit = () => {
      const box = wrap.current?.getBoundingClientRect();
      if (box) setScale(Math.min(box.width / STAGE_W, box.height / STAGE_H));
    };
    fit();
    const observer = new ResizeObserver(fit);
    if (wrap.current) observer.observe(wrap.current);
    return () => observer.disconnect();
  }, []);
  // 강조할 요소 위치를 재서 스포트라이트를 그 위에 둔다(화면 좌표 → 축소 전 좌표).
  // 화면 전환 효과와 사진 로딩으로 크기가 바뀌므로 잠깐 사이에 몇 번 더 잰다.
  useLayoutEffect(() => {
    const measure = () => {
      const base = stage.current?.getBoundingClientRect();
      const target = step.target ? stage.current?.querySelector(`[data-tour="${step.target}"]`) : null;
      if (!base || !target) return setSpot(null);
      const rect = target.getBoundingClientRect();
      const ratio = base.width / STAGE_W;
      setSpot({ x: (rect.left - base.left) / ratio, y: (rect.top - base.top) / ratio, w: rect.width / ratio, h: rect.height / ratio });
    };
    const frame = requestAnimationFrame(measure);
    const timers = [350, 900].map((ms) => window.setTimeout(measure, ms));
    return () => { cancelAnimationFrame(frame); timers.forEach(clearTimeout); };
  }, [index, scale, step.target]);

  const hintBelow = spot ? spot.y + spot.h + 70 < STAGE_H : true;
  return (
    <div className="tour-root" style={{ "--cap-h": `${CAPTION_H}px` } as React.CSSProperties}>
      <div className="tour-wrap" ref={wrap}>
        <div className="tour-stage" ref={stage} style={{ width: STAGE_W, height: STAGE_H, transform: `translate(-50%, -50%) scale(${scale})` }}>
          <ScreenView step={step} view={view} />
          {spot && (
            <>
              <div className={`tour-spot${step.click ? " click" : ""}${pressing ? " pressing" : ""}`} style={{ left: spot.x - 8, top: spot.y - 8, width: spot.w + 16, height: spot.h + 16 }}
                onClick={advance} role="button" aria-label={step.hint ?? "다음"} />
              {step.hint && (
                <div className={`tour-hint ${hintBelow ? "below" : "above"}`} style={{ left: Math.min(Math.max(spot.x + spot.w / 2, 120), STAGE_W - 120), top: hintBelow ? spot.y + spot.h + 18 : spot.y - 18 }}>
                  {step.click && (
                    <svg className="tour-hand" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 2l14 9-6 1.5 3.5 7-2.6 1.3-3.5-7L6 18Z" /></svg>
                  )}
                  <b>{index + 1}</b> {step.hint}
                </div>
              )}
            </>
          )}
        </div>
      </div>
      <div className="tour-caption" aria-live="polite">
        <span className={`tour-role ${step.role}`}>{step.role === "farm" ? "농가 관리자" : "구매자"}</span>
        <p key={index}>{step.caption}</p>
      </div>
    </div>
  );
}

function ScreenView({ step, view }: { step: Step; view: View }) {
  switch (step.screen) {
    case "console": return <ConsoleScreen view={view} />;
    case "market-farm": return <MarketFarm view={view} />;
    case "login": return <LoginScreen />;
    case "market-buyer": return <MarketBuyer view={view} />;
    case "pay": return <PayScreen view={view} />;
    case "dispatch": return <DispatchScreen view={view} />;
    default: return <SummaryScreen />;
  }
}

function AppBar({ role, active }: { role: Role; active: string }) {
  const items: [string, "camera" | "document" | "market" | "truck"][] = role === "farm"
    ? [["품질 검사", "camera"], ["품질 관리", "document"], ["입찰 시장", "market"], ["차량 관제", "truck"]]
    : [["입찰 시장", "market"], ["내 낙찰·결제", "document"]];
  return (
    <header className="app-header tour-app-header">
      <div className="brand"><Icon name="apple" /><div><strong>CQC 스마트 APC</strong></div></div>
      <nav>
        {items.map(([label, icon]) => <span key={label} className={label === active ? "active" : ""}><Icon name={icon} />{label}</span>)}
      </nav>
      <span className={`tour-user ${role}`}>{role === "farm" ? "CQC 사과농장 · 관리자" : "시연 마트 · 구매자"}</span>
    </header>
  );
}

function Frames({ apple, count = 12, big = false }: { apple: (typeof sampleApples)[number]; count?: number; big?: boolean }) {
  return (
    <div className={`tour-frames${big ? " big" : ""}`}>
      {apple.images.slice(0, count).map((src, i) => (
        <div key={src}><Image src={src} alt={`프레임 ${i + 1}`} width={160} height={160} unoptimized /><span>{String(i + 1).padStart(2, "0")}</span></div>
      ))}
    </div>
  );
}

function ConsoleScreen({ view }: { view: View }) {
  const pct = (a: number, b: number) => ((a / b) * 100).toFixed(1);
  return (
    <div className="tour-screen tour-console">
      <div className="qc-top tour-qc-top">
        <h1>CQC 사과농장 품질 관제</h1>
        <span className="qc-line">우리 농장 전용 · 선별 라인 1</span>
        <Badge tone="success">서버 관제</Badge>
        <div className="qc-lights" data-tour="lights">
          {["촬영 장치", "Inference", "Backend", "MySQL"].map((name) => <span key={name} className="qc-light success" title={name}><i /></span>)}
        </div>
      </div>
      <section className="tour-kpis" data-tour="kpis">
        <article><p>오늘 검사 수</p><strong>{view.total.toLocaleString("ko-KR")}건</strong></article>
        <article className="warn"><p>오늘 재검사율</p><strong>{pct(view.reinspection, view.total)}%<small> {view.reinspection}건</small></strong></article>
        <article className="err"><p>오늘 오류율</p><strong>{pct(view.errors, view.total)}%<small> {view.errors}건</small></strong></article>
      </section>
      <div className="tour-console-body">
        <div className="tour-col">
          <Panel title="처리 중 사과" icon="camera" action={<Badge tone="success">입력 중 · 2초 간격</Badge>}>
            <div data-tour="jobs" className={`tour-jobs ${view.apple}`}>
              {view.apple === "idle" ? <div className="tour-empty">다음 사과를 기다리는 중</div> : <Frames apple={MAIN} big />}
              <div className="tour-job-info" data-tour="result">
                <strong>12:14:31 투입</strong>
                {view.apple === "shoot" && <span>12장 촬영 · 판정 중…</span>}
                {view.apple === "judged" && <span className="ok">판정 완료 · <b>부사 특</b> · 품질 신뢰도 97.8% · 가상 당도 15.1 → 선별함 02</span>}
              </div>
            </div>
          </Panel>
          <Panel title="재검사·오류 사과" icon="alert">
            <div data-tour="exception" className="tour-exceptions">
              {view.review && (
                <div className="tour-review fresh">
                  <Image src={REVIEW.images[0]} alt="재검사 사과" width={64} height={64} unoptimized />
                  <span>12:14:33</span><Badge tone="warning">재검사</Badge><span>품질 신뢰도 미달 · 양광 / 보통 · 100.0% / 48.9%</span><b>재검사함</b>
                </div>
              )}
              <div className="tour-review"><span>12:13:56</span><Badge tone="warning">재검사</Badge><span>품질 신뢰도 미달 · 부사 / 상 · 100.0% / 58.6%</span><b>재검사함</b></div>
              <div className="tour-review"><span>12:13:42</span><Badge tone="warning">재검사</Badge><span>품질 신뢰도 미달 · 부사 / 특 · 100.0% / 55.8%</span><b>재검사함</b></div>
            </div>
          </Panel>
        </div>
        <Panel title="처리 현황" icon="market">
          <div className="tour-trend">
            <div className="tour-period"><strong>30건</strong><span>최근 1분 저장</span></div>
            <svg viewBox="0 0 600 180" className="tour-chart" aria-hidden="true">
              <path d="M0 90 H180 V120 H210 V90 H250 L258 70 L266 90 H600" fill="none" stroke="#ae525c" strokeWidth="3" />
              <path d="M0 90 H600" stroke="#ccc" strokeDasharray="6 6" />
            </svg>
            <div className="tour-bins">
              <div className="tour-bins-head"><strong>오늘 선별함</strong><small>★ 못난이 사과 후보</small></div>
              <div className="tour-bin-grid">
                {[["부사", [423, view.bin02, 301, 659, 420, 402]], ["양광", [369, 469, 287, 250, 307, 527]]].map(([variety, counts]) => (
                  <div key={variety as string} className="tour-bin-row">
                    <span>{variety as string}</span>
                    {(counts as number[]).map((value, i) => {
                      const no = String(i + 1 + (variety === "양광" ? 6 : 0)).padStart(2, "0");
                      return <div key={no} data-tour={`bin-${no}`} className={`tour-bin${no === "06" || no === "12" ? " ugly" : ""}${view.recentBin === no ? " recent" : ""}`}><small>{no}</small><b>{value}</b></div>;
                    })}
                  </div>
                ))}
                <div className={`tour-bin review${view.recentBin === "re" ? " recent" : ""}`}><small>재검사함</small><b>{view.reinspection}</b></div>
              </div>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function LotCard({ view, buyer = false }: { view: View; buyer?: boolean }) {
  return (
    <div className="tour-lot" data-tour={buyer ? "lot-buyer" : "lot-farm"}>
      <Image src={MAIN.images[0]} alt="출품 사과" width={96} height={96} unoptimized />
      <div>
        <strong>lot-0213a7 <Badge tone={view.lotOpen ? "success" : "neutral"}>{view.lotOpen ? "경매 중" : view.won ? "낙찰" : "대기"}</Badge></strong>
        <span>부사 · 특 · 2개 묶음(선별함 02)</span>
        <span>판정 신뢰도 97.8% · 가상 당도 15.1</span>
        <span>최저가 <b>5,000원</b></span>
      </div>
    </div>
  );
}

function MarketFarm({ view }: { view: View }) {
  return (
    <div className="tour-screen">
      <AppBar role="farm" active="입찰 시장" />
      <div className="tour-body two">
        <Panel title="출품할 수 있는 묶음" icon="box">
          <div className="tour-ready">
            <Frames apple={MAIN} count={6} />
            <p>선별함 02 · 부사 특 · 당도 높음 · <b>2개 모임</b></p>
            {!view.lotListed && <button className="primary-button" data-tour="list-btn">출품하기</button>}
            {view.lotListed && <p className="ok">출품 완료 · 경매 진행 중</p>}
          </div>
        </Panel>
        <Panel title="내 출품" icon="market">
          {view.lotListed ? <LotCard view={view} /> : <div className="tour-empty">아직 출품한 묶음이 없습니다.</div>}
        </Panel>
      </div>
    </div>
  );
}

function LoginScreen() {
  return (
    <div className="tour-screen tour-login">
      <div className="tour-login-card">
        <div className="brand"><Icon name="apple" /><div><strong>CQC 스마트 APC</strong></div></div>
        <div className="tour-tabs"><span>농가</span><span className="active">구매자</span></div>
        <label>아이디<input readOnly value="demo-mart" /></label>
        <label>비밀번호<input readOnly type="password" value="demo-pass" /></label>
        <button className="primary-button" data-tour="login-btn">구매자로 로그인</button>
      </div>
    </div>
  );
}

function MarketBuyer({ view }: { view: View }) {
  const bids = [
    ...(view.bidPlaced ? [{ who: "시연 마트(나)", price: 6500, me: true }] : []),
    ...(view.rivals ? [{ who: "시연 식당", price: 6000, me: false }, { who: "시연 유통사", price: 5500, me: false }] : []),
  ];
  return (
    <div className="tour-screen">
      <AppBar role="buyer" active="입찰 시장" />
      {view.won && <div className="tour-won" data-tour="won"><Icon name="check" /> 낙찰되었습니다 · lot-0213a7 · 6,500원 · 결제를 진행해 주세요</div>}
      <div className="tour-body three">
        <Panel title="경매 중인 출품" icon="market"><LotCard view={view} buyer /></Panel>
        <Panel title="출품 상세" icon="apple"><Frames apple={MAIN} /></Panel>
        <Panel title="실시간 입찰" icon="clock" action={<Badge tone={view.lotOpen ? "success" : "neutral"}>{view.lotOpen ? "마감 6초 전" : "마감"}</Badge>}>
          <div className="tour-bid-form">
            <label>입찰 금액<input readOnly value="6,500" /> 원</label>
            <button className="primary-button" data-tour="bid-btn" disabled={view.bidPlaced}>{view.bidPlaced ? "입찰 완료" : "입찰하기"}</button>
          </div>
          <table className="tour-bids" data-tour="bids">
            <thead><tr><th>순위</th><th>입찰자</th><th>금액</th></tr></thead>
            <tbody>
              {bids.length ? bids.map((bid, i) => <tr key={bid.who} className={bid.me ? "me" : ""}><td>{i + 1}</td><td>{bid.who}</td><td>{bid.price.toLocaleString("ko-KR")}원</td></tr>)
                : <tr><td colSpan={3}>첫 입찰을 기다리고 있습니다.</td></tr>}
            </tbody>
          </table>
        </Panel>
      </div>
    </div>
  );
}

function PayScreen({ view }: { view: View }) {
  return (
    <div className="tour-screen">
      <AppBar role="buyer" active="내 낙찰·결제" />
      <div className="tour-body two">
        <Panel title="낙찰 주문" icon="document">
          <dl className="tour-order">
            <div><dt>출품</dt><dd>lot-0213a7 · 부사 특 2개</dd></div>
            <div><dt>낙찰가</dt><dd>6,500원</dd></div>
            <div><dt>판매 농가</dt><dd>CQC 사과농장</dd></div>
            <div><dt>배송지</dt><dd>시연 마트 물류센터</dd></div>
          </dl>
        </Panel>
        <Panel title="결제" icon="check">
          {!view.paid ? (
            <div className="tour-pay">
              <div className="tour-methods"><span className="active">카드</span><span>간편결제</span><span>계좌이체</span></div>
              <p>테스트 결제입니다. 실제 돈은 나가지 않습니다.</p>
              <button className="primary-button" data-tour="pay-btn">6,500원 결제하기</button>
            </div>
          ) : (
            <div className="tour-pay done" data-tour="pay-done">
              <Icon name="check" /><strong>결제 완료</strong><span>카드 · 테스트 승인 · 12:15:02</span><span>농가에 배차 요청을 보냈습니다.</span>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

function DispatchScreen({ view }: { view: View }) {
  return (
    <div className="tour-screen">
      <AppBar role="farm" active="차량 관제" />
      <div className="tour-body two">
        <Panel title="배차 대기 주문" icon="document">
          <table className="tour-bids">
            <thead><tr><th>주문</th><th>구매자</th><th>금액</th><th>상태</th><th /></tr></thead>
            <tbody><tr>
              <td>order-0213a7</td><td>시연 마트</td><td>6,500원</td>
              <td><Badge tone={view.dispatched ? "success" : "warning"}>{view.dispatched ? "배차 완료" : "결제 완료 · 배차 대기"}</Badge></td>
              <td>{!view.dispatched && <button className="primary-button" data-tour="dispatch-btn">배차하기</button>}</td>
            </tr></tbody>
          </table>
        </Panel>
        <Panel title="차량" icon="truck">
          <div className="tour-route" data-tour="route">
            <div className="tour-route-line">
              <span className="end">CQC 사과농장</span>
              <i className={view.dispatched ? "moving" : ""}><Icon name="truck" /></i>
              <span className="end">시연 마트</span>
            </div>
            {view.dispatched ? <p><b>CQC-01</b> 배정 · 적재 2개 · 출발</p> : <p>유휴 차량 3대 · 가장 가까운 차량을 배정합니다.</p>}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function SummaryScreen() {
  const items: [string, string, ReactNode][] = [
    ["12:14:31", "촬영", "촬영 장치 · 12장"],
    ["12:14:31", "판정", "부사 특 · 신뢰도 97.8%"],
    ["12:14:31", "선별", "선별함 02"],
    ["12:14:48", "출품", "농가 · lot-0213a7"],
    ["12:14:52", "입찰", "구매자 3곳"],
    ["12:14:58", "낙찰", "시연 마트 · 6,500원"],
    ["12:15:02", "결제", "테스트 결제 승인"],
    ["12:15:06", "배차", "CQC-01 출발"],
  ];
  return (
    <div className="tour-screen tour-summary" data-tour="summary">
      <h1>사과 한 개의 하루</h1>
      <ol>
        {items.map(([time, name, detail], i) => (
          <li key={name} className={i < 3 ? "farm" : i < 4 ? "farm" : i < 7 ? "buyer" : "farm"}>
            <time>{time}</time><strong>{name}</strong><span>{detail}</span>
          </li>
        ))}
      </ol>
      <p><span className="farm">농가 관리자</span> 촬영·판정·선별·출품·배차 · <span className="buyer">구매자</span> 입찰·낙찰·결제</p>
    </div>
  );
}
