"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

/** Keep the inspection console in the viewport while letting its panels manage their own overflow. */
export default function QualityViewport({ children }: { children: ReactNode }) {
  if (usePathname() !== "/") return children;
  return <div className="quality-viewport">
    <div className="quality-canvas">{children}</div>
  </div>;
}
