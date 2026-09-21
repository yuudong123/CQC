import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CQC 물류 관제센터",
  description: "CQC 기반 B2B 농산물 자동배차 관제 플랫폼",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}

