"use client";

import Image from "next/image";
import { useState } from "react";
import { Badge, Icon, Panel, Stats } from "@/components/Dashboard";
import { sampleApples } from "@/lib/sample-apples";
import { qualityBins } from "@/lib/quality-bins";

const inspections = Array.from({ length: 12 }, (_, i) => ({
  id: `SAMPLE-${String(12 - i).padStart(4, "0")}`,
  apple: sampleApples[[5, 4, 0, 3, 1, 2][i % 6]],
  confidence: [94.2, 91.1, 86.5, 78.3, 62.1, 92.7, 95.1, 86.6, 90.3, 93.8, 87.6, 91.8][i],
  virtualBrix: [14.1, 13.3, 11.9, 12.0, 15.2, 13.8][i % 6],
  state: i === 3 ? "REVIEW" : i === 4 ? "QC FAIL" : "QC PASS",
  time: `14:32:${String(12 - i).padStart(2, "0")}`,
}));
const issues = inspections.filter(item => item.state !== "QC PASS");
const label = (state: string) => state === "QC PASS" ? "통과" : state === "REVIEW" ? "검수 대기" : "불합격 확인";
const tone = (state: string) => state === "QC PASS" ? "success" : state === "REVIEW" ? "warning" : "danger";

export default function QualityPage() {
  const [selectedId, setSelectedId] = useState(issues[0].id);
  const [view, setView] = useState(0);
  const selected = issues.find(item => item.id === selectedId)!;
  const reviewCount = issues.filter(item => item.state === "REVIEW").length;
  const failCount = issues.filter(item => item.state === "QC FAIL").length;
  const passCount = inspections.length - issues.length;
  return <main className="dashboard quality-page operations-page">
    <div className="ops-heading"><h1>품질 검사 관제</h1><Badge tone="warning">샘플 화면</Badge><span>판정은 예시 데이터 · 실시간 검사 연동 전</span></div>
    <Stats items={[
      { label: "검수 대기", value: `${reviewCount}건`, icon: "document", tone: "warning" },
      { label: "불합격 확인", value: `${failCount}건`, icon: "alert", tone: "danger" },
      { label: "최장 검수 대기", value: "미측정", icon: "clock" },
      { label: "처리 속도", value: "— 건/초", icon: "market" },
      { label: "설비 장애", value: "확인 대기", icon: "box" },
    ]}/>
    <div className="ops-connection"><Icon name="alert"/><strong>실시간 상태 확인 불가</strong><span>영상 수신 · 추론 · 선별기 모두 연동 대기</span><span className="ops-last">마지막 수신 —</span></div>
    <div className="ops-main">
      <Panel title="확인 필요한 사과" icon="alert" action={<Badge tone="danger">{issues.length}건 미확인 · 예시</Badge>} className="ops-queue">
        <div className="queue-header"><span>판정 / 확인 사유</span><span>발생 시각</span></div>
        {issues.map(item => <button type="button" className={`issue-card ${selectedId === item.id ? "selected" : ""}`} key={item.id} onClick={() => { setSelectedId(item.id); setView(0); }} aria-pressed={selectedId === item.id} aria-label={`${item.id} ${label(item.state)}`}>
          <Image src={item.apple.images[0]} alt={`${item.apple.variety} 확인 대상 사과`} width={160} height={160}/>
          <div className="issue-info"><Badge tone={tone(item.state)}>{label(item.state)}</Badge><strong>{item.state === "REVIEW" ? "낮은 신뢰도 · 관리자 검수 필요" : "불합격 판정 · 결과 확인 필요"}</strong><small>{item.apple.variety} · 신뢰도 {item.confidence}% · {item.id}</small></div>
          <div className="issue-time"><time>{item.time}</time><small>대기 시간 미측정</small><Icon name="arrow"/></div>
        </button>)}
        <div className="queue-summary"><span>정상 통과 <b>{passCount}건</b></span><span>확인 대상 <b>{issues.length}건</b></span><span>표본 <b>{inspections.length}건</b></span></div>
      </Panel>
      <Panel title="선택 항목 확인" icon="camera" action={<Badge tone={tone(selected.state)}>{label(selected.state)}</Badge>}>
        <div className="ops-detail"><div className="ops-photo"><Image src={selected.apple.images[view]} alt={`${selected.apple.variety} 확인 사진 ${view + 1}`} width={640} height={640}/><div className="ops-views">{selected.apple.images.map((src, i) => <button key={src} type="button" onClick={() => setView(i)} aria-label={`촬영 ${i + 1} 보기`} aria-pressed={view === i}>{i + 1}</button>)}</div></div>
          <div className="ops-evidence"><h3>{selected.state === "REVIEW" ? "등급 확정 전 검수가 필요합니다" : "불합격 판정을 확인해 주세요"}</h3><dl><dt>사과</dt><dd>{selected.apple.variety} · {selected.id}</dd><dt>판정 시각</dt><dd>{selected.time}</dd><dt>신뢰도</dt><dd>{selected.confidence}%</dd><dt>확인 사유</dt><dd>{selected.state === "REVIEW" ? "저신뢰 판정" : "QC 실패 · 상세 사유 미제공"}</dd><dt>가상 당도</dt><dd>{selected.virtualBrix.toFixed(1)} °Brix · 실측 아님</dd><dt>당도 구간</dt><dd>{selected.virtualBrix < 12 ? "12° 미만" : "12° 이상"} · 시연 예시</dd><dt>후속 처리</dt><dd>품질 재확인</dd></dl><p className="ops-pending">검수 확정 기능 연동 대기</p></div>
        </div>
      </Panel>
    </div>
    <div className="ops-bottom">
      <Panel title="최근 판정" icon="clock" action={<small>최근 6건 · 예시 시각</small>}><table><thead><tr><th>시각</th><th>품종</th><th>판정</th><th>등급</th><th>신뢰도</th></tr></thead><tbody>{inspections.slice(0,6).map(item => <tr key={item.id}><td>{item.time}</td><td>{item.apple.variety}</td><td>{item.state === "QC PASS" ? <Badge tone="success">통과</Badge> : <button type="button" className="table-link" onClick={() => { setSelectedId(item.id); setView(0); }}><Badge tone={tone(item.state)}>{label(item.state)} ↗</Badge></button>}</td><td>{item.state === "QC PASS" ? item.apple.grade : "—"}</td><td>{item.confidence}%</td></tr>)}</tbody></table></Panel>
      <Panel title="선별함 상태" icon="box" action={<Badge>정상 12개 · 재검사 1개</Badge>}><div className="ops-bin-grid">{qualityBins.map(bin => <div className="ops-bin-card" key={bin.code}><strong>{bin.variety} · {bin.grade}</strong><span>가상 당도 {bin.sweetness}</span><small>{bin.code}</small><span>적재량 — · 연동 대기</span></div>)}</div><div className="ops-reinspection"><strong>재검사함</strong><span>저신뢰 · 시간 초과 · 오류 · 가상 당도 누락</span><small>TEST_REINSPECTION_BIN · 적재량 —</small></div><p className="ops-note">가상 당도는 실측 아님 · 적재량과 물량 집계는 연결 후 표시됩니다.</p></Panel>
      <Panel title="품질 요약" icon="market" action={<small>샘플 {inspections.length}건 기준</small>}><div className="ops-rates"><div><span>통과</span><strong>{(passCount/inspections.length*100).toFixed(1)}<small>%</small></strong></div><div><span>검수 대상</span><strong>{(reviewCount/inspections.length*100).toFixed(1)}<small>%</small></strong></div><div><span>불합격</span><strong>{(failCount/inspections.length*100).toFixed(1)}<small>%</small></strong></div></div><div className="ops-distribution" aria-label={`통과 ${passCount}건, 검수 ${reviewCount}건, 불합격 ${failCount}건`}><span style={{flex:passCount}}/><span style={{flex:reviewCount}}/><span style={{flex:failCount}}/></div><div className="ops-trend"><Icon name="clock"/><div><strong>시간대별 변화 · 연동 대기</strong><p>추이와 급증 여부를 확인할 실시간 데이터가 없습니다.</p></div></div></Panel>
    </div>
  </main>;
}
