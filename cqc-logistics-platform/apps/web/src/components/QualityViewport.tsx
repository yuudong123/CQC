"use client";

import { usePathname } from "next/navigation";
import { useLayoutEffect, useRef, useState, type ReactNode } from "react";

/** Fit the entire inspection console, including expanded history, in the viewport. */
export default function QualityViewport({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const viewport = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLDivElement>(null);
  const [fit, setFit] = useState({ scale: 1, left: 0, top: 0 });
  const enabled = pathname === "/";

  useLayoutEffect(() => {
    if (!enabled || !viewport.current || !canvas.current) return;
    const outer = viewport.current;
    const inner = canvas.current;
    const resize = () => {
      const width = inner.offsetWidth;
      const height = inner.scrollHeight + 2;
      const bounds = outer.getBoundingClientRect();
      const scale = Math.min(bounds.width / width, bounds.height / height);
      const next = {
        scale,
        left: Math.max(0, (bounds.width - width * scale) / 2),
        top: Math.max(0, (bounds.height - height * scale) / 2),
      };
      setFit(current => current.scale === next.scale && current.left === next.left && current.top === next.top ? current : next);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(outer);
    observer.observe(inner);
    resize();
    return () => observer.disconnect();
  }, [enabled]);

  if (!enabled) return children;
  return <div className="quality-viewport" ref={viewport}>
    <div className="quality-canvas" ref={canvas} style={{ transform: `translate(${fit.left}px, ${fit.top}px) scale(${fit.scale})` }}>{children}</div>
  </div>;
}
