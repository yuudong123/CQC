import type { Metadata } from "next";
import TourDemo from "@/components/TourDemo";
import "./tour.css";

// 통합 흐름 시연 전용 페이지. 실제 API를 부르지 않는 각본 화면이라 메뉴에는 넣지 않고 주소(/tour)로만 연다.
export const metadata: Metadata = { title: "CQC 통합 흐름 시연" };

export default function TourPage() {
  return <TourDemo />;
}
