import type { Metadata } from "next";
import TourDemo from "@/components/TourDemo";
import "./tour.css";

// 통합 흐름 시연 안내. 실제 화면 위에 노란 테두리와 자막만 얹는다. 메뉴에는 넣지 않고 주소(/tour)로만 연다.
export const metadata: Metadata = { title: "CQC 통합 흐름 시연" };

export default function TourPage() {
  return <TourDemo />;
}
