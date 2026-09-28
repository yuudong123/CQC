import type { Metadata } from "next";
import "./globals.css";
import { AppHeader } from "@/components/Dashboard";
import QualityViewport from "@/components/QualityViewport";

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
        <QualityViewport>
          <AppHeader />
          {children}
        </QualityViewport>
      </body>
    </html>
  );
}
