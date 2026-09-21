import GoogleFleetMap from "@/components/GoogleFleetMap";

const stats = [
  { label: "진행 중 경매", value: "2", tone: "blue" },
  { label: "운행 차량", value: "3 / 5", tone: "green" },
  { label: "배송 중 물량", value: "1,240 kg", tone: "orange" },
  { label: "확인 필요", value: "1", tone: "red" },
] as const;

const deliveries = [
  { crop: "부사 · 특", route: "아산 → 서울", state: "상차 대기", truck: "CQC-01" },
  { crop: "양광 · 상", route: "충주 → 수원", state: "배송 중", truck: "CQC-03" },
  { crop: "부사 · 상", route: "아산 → 대전", state: "낙찰 완료", truck: "배차 중" },
] as const;

export default function Home() {
  return (
    <main>
      <header className="topbar">
        <div>
          <p className="eyebrow">CROP QUALITY CHECK × LOGISTICS</p>
          <h1>CQC 물류 관제센터</h1>
        </div>
        <div className="system-status"><span /> 전체 시스템 정상</div>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow">TODAY&apos;S OPERATION</p>
          <h2>품질 판정에서 배송까지,<br />하나의 흐름으로 관리합니다.</h2>
          <p className="hero-copy">CQC 판정 결과를 출품·낙찰·자동배차와 연결하는 데모 관제 화면입니다.</p>
        </div>
        <div className="hero-actions">
          <a className="hero-button" href="/market">입찰 시장 열기</a>
          <a className="hero-button secondary" href="/control">차량 관제 열기</a>
        </div>
      </section>

      <section className="stats" aria-label="운영 현황">
        {stats.map((stat) => (
          <article className={`stat ${stat.tone}`} key={stat.label}>
            <p>{stat.label}</p>
            <strong>{stat.value}</strong>
          </article>
        ))}
      </section>

      <section className="grid">
        <article className="panel map-panel">
          <div className="panel-title">
            <div><p className="eyebrow">LIVE FLEET</p><h3>실시간 차량 위치</h3></div>
            <span>2초마다 갱신</span>
          </div>
          <GoogleFleetMap />
        </article>

        <article className="panel">
          <div className="panel-title">
            <div><p className="eyebrow">DELIVERIES</p><h3>주문·배송 현황</h3></div>
            <button className="text-button" type="button">전체 보기</button>
          </div>
          <div className="delivery-list">
            {deliveries.map((item) => (
              <div className="delivery" key={`${item.crop}-${item.route}`}>
                <div><strong>{item.crop}</strong><p>{item.route}</p></div>
                <div className="delivery-meta"><span>{item.state}</span><small>{item.truck}</small></div>
              </div>
            ))}
          </div>
        </article>
      </section>
    </main>
  );
}
