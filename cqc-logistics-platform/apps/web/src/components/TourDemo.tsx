"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * 통합 흐름 시연 안내(/tour). 실제 화면(관제·구매자·판매자·차량 관제)을 그대로 띄우고, 그 위에 노란 테두리와 자막만 얹는다.
 * 화면과 데이터는 실제 페이지 그대로라 없는 기능이 나오지 않는다. 출품·입찰·낙찰·결제는 구매자 화면 자동 시연이 실제로 진행한다.
 * 넘기기: 노란 테두리 안의 버튼을 직접 누르거나 → · Space · Enter, 이전 단계는 ←. 누르는 단계는 실제 버튼을 눌러야 진행한다.
 */

type Target = { selector: string } | { panel: string };
type Step = {
  route: string;
  role: "farm" | "buyer";
  target?: Target;
  hint?: string;
  /** 노란 테두리 안의 실제 버튼을 눌러 진행하는 단계 */
  click?: boolean;
  /** 이 요소가 나타나면 자동으로 다음 단계로 넘어간다 */
  until?: string;
  caption: string;
};

const STEPS: Step[] = [
  { route: "/", role: "farm", target: { selector: ".qc-lights" }, hint: "설비 상태",
    caption: "먼저 농가가 보는 품질 관제 화면입니다. 위쪽 점 네 개는 촬영 장치, 판정 서버, 관제 서버, 데이터베이스 상태이고, 모두 초록이면 정상입니다." },
  { route: "/", role: "farm", target: { selector: ".qc-jobs-panel" }, hint: "처리 중 사과",
    caption: "라인에 들어온 사과 한 개의 열두 각도 사진입니다. 시연에서는 촬영 장치 대신 데이터셋 사진 열두 장을 2초마다 넣습니다." },
  { route: "/", role: "farm", target: { selector: ".qc-binmap" }, hint: "오늘 선별함",
    caption: "AI가 판정한 품종과 외관 등급에 가상 당도를 더해 선별함 열두 칸 중 하나로 보냅니다. 방금 들어간 칸은 테두리가 반짝이고, 별표 칸은 못난이 사과 후보입니다." },
  { route: "/", role: "farm", target: { selector: ".qc-exception-panel" }, hint: "재검사·오류 사과",
    caption: "신뢰도가 기준보다 낮은 사과는 판정하지 않고 재검사함으로 보냅니다. 여기서 사유와 신뢰도를 확인합니다." },
  { route: "/", role: "farm", target: { selector: ".qc-kpis" }, hint: "오늘 숫자",
    caption: "위쪽 큰 숫자 세 개가 오늘 검사 수, 재검사율, 오류율입니다. 농가는 이 숫자로 오늘 라인 상태를 한눈에 확인합니다." },
  { route: "/market/buyer", role: "buyer", target: { selector: ".buyer-header" }, hint: "구매자 화면",
    caption: "이제 구매자 화면입니다. 농가 메뉴 없이 출품 확인과 입찰만 하는 별도 화면입니다." },
  { route: "/market/buyer", role: "buyer", target: { selector: ".auto-demo-heading button" }, hint: "여기를 누릅니다", click: true,
    caption: "자동 시연을 시작하겠습니다. 같은 선별함에 통과한 사과 두 개가 모이면 출품되고, 가상 구매자들이 6초 동안 입찰합니다." },
  { route: "/market/buyer", role: "buyer", target: { selector: ".auto-auction-demo" }, hint: "출품·입찰 진행", until: ".payment-popup",
    caption: "출품과 입찰 기록이 실시간으로 올라옵니다. 경매가 끝나면 최고가 입찰자에게 낙찰됩니다." },
  { route: "/market/buyer", role: "buyer", target: { selector: ".payment-popup .payment-actions button" }, hint: "결제하기", click: true,
    caption: "낙찰되면 낙찰자 화면에 결제 창이 뜹니다. 결제하기를 누르면 토스페이먼츠 테스트 결제창이 열립니다. 테스트 결제라 실제 돈은 나가지 않습니다." },
  { route: "/market/buyer", role: "buyer", target: { selector: ".payment-popup .paid" }, hint: "결제 완료",
    caption: "결제가 승인되면 결제 완료가 뜨고, 자동 시연이 이 주문에 차량 배정을 요청합니다." },
  { route: "/market", role: "farm", target: { selector: ".auction-result" }, hint: "경매 결과",
    caption: "판매자인 농가 화면입니다. 농가는 직접 낙찰하지 않고, 마감 정보와 최근 낙찰 결과만 확인합니다." },
  { route: "/market", role: "farm", target: { selector: ".market-admin-actions" }, hint: "사업자 등록",
    caption: "실제 서비스에서 결제 대금을 받으려면 농장의 사업자 등록과 PG 가맹이 필요해서, 등록 화면을 준비해 두었습니다." },
  { route: "/control", role: "farm", target: { panel: "차량 현황" }, hint: "차량 현황",
    caption: "결제가 끝난 주문에 배정된 차량을 차량 관제에서 확인합니다. 차량별 적재량과 상태가 보입니다." },
  { route: "/control", role: "farm", target: { panel: "배송 경로" }, hint: "배송 경로",
    caption: "배정된 차량의 픽업과 배송 경로입니다. 사과 한 개가 촬영부터 판정, 선별, 출품, 낙찰, 결제, 배차까지 하나의 흐름으로 이어졌습니다." },
];
const CAPTION_H = 96;

function findTarget(doc: Document, target: Target): Element | null {
  if ("selector" in target) return doc.querySelector(target.selector);
  return [...doc.querySelectorAll("section.panel")].find((panel) => panel.querySelector("h2")?.textContent?.includes(target.panel)) ?? null;
}

export default function TourDemo() {
  const [index, setIndex] = useState(0);
  const [spot, setSpot] = useState<{ x: number; y: number; w: number; h: number; vw: number; vh: number } | null>(null);
  const frame = useRef<HTMLIFrameElement>(null);
  const step = STEPS[index];

  const go = useCallback((next: number) => setIndex(Math.max(0, Math.min(STEPS.length - 1, next))), []);
  const advance = useCallback(() => go(index + 1), [go, index]);

  // 단계의 화면 주소가 바뀌면 그 실제 페이지를 연다.
  useEffect(() => {
    const iframe = frame.current;
    if (iframe && iframe.contentWindow?.location.pathname !== step.route) iframe.src = step.route;
  }, [step.route]);

  // 강조할 실제 요소를 찾아 보이게 하고 위치를 잰다. 실제 화면이 계속 갱신되므로 주기적으로 다시 잰다.
  useEffect(() => {
    let scrolled = false;
    const measure = () => {
      const doc = frame.current?.contentDocument;
      const element = doc && step.target ? findTarget(doc, step.target) : null;
      if (!doc || !element) return setSpot(null);
      if (!scrolled) { element.scrollIntoView({ block: "center", inline: "nearest" }); scrolled = true; }
      const rect = element.getBoundingClientRect();
      setSpot({ x: rect.left, y: rect.top, w: rect.width, h: rect.height, vw: doc.documentElement.clientWidth, vh: doc.documentElement.clientHeight });
      if (step.until && doc.querySelector(step.until)) advance();
    };
    const timer = window.setInterval(measure, 400);
    return () => clearInterval(timer);
  }, [step, advance]);

  // 키보드와, 실제 화면 안에서 강조된 버튼을 누른 것을 듣는다.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "ArrowRight" || event.key === " " || event.key === "Enter") {
        if (step.click) return; // 누르는 단계는 실제 버튼을 눌러야 진행한다
        event.preventDefault(); advance();
      } else if (event.key === "ArrowLeft") go(index - 1);
    };
    const onClick = (event: MouseEvent) => {
      const doc = frame.current?.contentDocument;
      const element = doc && step.target ? findTarget(doc, step.target) : null;
      // iframe 안의 요소는 바깥 창의 Node와 다른 realm이라 instanceof 대신 contains로만 확인한다.
      if (step.click && element && event.target && element.contains(event.target as Node)) window.setTimeout(advance, 300);
    };
    const iframe = frame.current;
    let attached: Window | null = null;
    const attach = () => {
      const win = iframe?.contentWindow;
      if (!win) return;
      win.addEventListener("keydown", onKey);
      win.document.addEventListener("click", onClick, true);
      attached = win;
    };
    const detach = () => {
      attached?.removeEventListener("keydown", onKey);
      attached?.document.removeEventListener("click", onClick, true);
    };
    window.addEventListener("keydown", onKey);
    attach();
    iframe?.addEventListener("load", attach);
    return () => { window.removeEventListener("keydown", onKey); iframe?.removeEventListener("load", attach); detach(); };
  }, [step, index, advance, go]);

  const hintBelow = spot ? spot.y + spot.h + 60 < spot.vh : true;
  return (
    <div className="tour-root" style={{ "--cap-h": `${CAPTION_H}px` } as React.CSSProperties}>
      <div className="tour-wrap">
        <iframe ref={frame} className="tour-frame" src={STEPS[0].route} title="CQC 실제 화면" />
        {spot && (
          <>
            <div className={`tour-spot${step.click ? " click" : ""}`} style={{ left: spot.x - 6, top: spot.y - 6, width: spot.w + 12, height: spot.h + 12 }} />
            {step.hint && (
              <div className={`tour-hint ${hintBelow ? "below" : "above"}`} style={{ left: Math.min(Math.max(spot.x + spot.w / 2, 110), spot.vw - 110), top: hintBelow ? spot.y + spot.h + 14 : spot.y - 14 }}>
                <b>{index + 1}</b> {step.hint}
              </div>
            )}
          </>
        )}
      </div>
      <div className="tour-caption" aria-live="polite">
        <span className={`tour-role ${step.role}`}>{step.role === "farm" ? "농가" : "구매자"}</span>
        <p key={index}>{step.caption}</p>
        <span className="tour-count">{index + 1} / {STEPS.length}</span>
      </div>
    </div>
  );
}
