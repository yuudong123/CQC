import type { Metadata } from "next";
import "./globals.css";
import "./quality-console.css";
import { AppHeader } from "@/components/Dashboard";
import QualityViewport from "@/components/QualityViewport";
import DemoProvider from "@/components/DemoProvider";

// 어떤 페이지로 직접 접속해도 배포 환경의 관제 연결 모드를 동일하게 적용합니다.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "CQC 스마트 APC",
  description: "CQC 기반 B2B 농산물 자동배차 관제 플랫폼",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>
        <DemoProvider mode={process.env.CQC_QUALITY_MODE === "api" ? "api" : "demo"}><QualityViewport>
          <AppHeader />
          {children}
        </QualityViewport></DemoProvider>
      </body>
    </html>
  );
}
