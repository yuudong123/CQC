"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

export type IconName =
  | "apple"
  | "camera"
  | "market"
  | "truck"
  | "clock"
  | "check"
  | "alert"
  | "box"
  | "document"
  | "arrow"
  | "pin";
export function Icon({
  name,
  className = "",
}: {
  name: IconName;
  className?: string;
}) {
  const paths: Record<IconName, ReactNode> = {
    apple: (
      <>
        <path
          d="M12 7C4 2 1 10 4 17c2 5 5 5 8 3 3 2 6 2 8-3 3-7 0-15-8-10Z"
          fill="currentColor"
          stroke="none"
        />
        <path d="M12 7V3m1 1c2-3 4-3 5-3-1 3-3 4-5 3Z" />
      </>
    ),
    camera: (
      <>
        <path d="m8 5 2-2h4l2 2h5v15H3V5Z" />
        <circle cx="12" cy="12" r="4" />
      </>
    ),
    market: (
      <>
        <path d="M4 20V12h3v8m4 0V7h3v13m4 0V3h3v17" />
      </>
    ),
    truck: (
      <>
        <path d="M2 5h12v12H2Zm12 5h4l4 4v3h-8" />
        <circle cx="6" cy="18" r="2" />
        <circle cx="18" cy="18" r="2" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 6v6l4 2" />
      </>
    ),
    check: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="m7 12 3 3 7-7" />
      </>
    ),
    alert: (
      <>
        <path d="m12 3 10 18H2ZM12 9v5m0 3v1" />
      </>
    ),
    box: (
      <>
        <path d="m12 2 10 5v10l-10 5-10-5V7Zm0 10 10-5M12 12 2 7m10 5v10M7 5l10 5" />
      </>
    ),
    document: (
      <>
        <path d="M5 2h9l5 5v15H5Zm9 0v6h5M8 12h8m-8 4h6" />
      </>
    ),
    arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
    pin: (
      <>
        <path d="M19 9c0 5-7 13-7 13S5 14 5 9a7 7 0 0 1 14 0Z" />
        <circle cx="12" cy="9" r="2" />
      </>
    ),
  };
  return (
    <svg
      className={`icon ${className}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}

export function AppHeader() {
  const pathname = usePathname();
  const [now, setNow] = useState<Date>();
  useEffect(() => {
    if (pathname === "/") return;
    const tick = () => setNow(new Date());
    const start = window.setTimeout(tick, 0);
    const timer = window.setInterval(tick, 1000);
    return () => {
      clearTimeout(start);
      clearInterval(timer);
    };
  }, [pathname]);
  if (pathname === "/") return null;
  return (
    <header className="app-header">
      <div className="brand">
        <Icon name="apple" />
        <div>
          <strong>CQC 스마트 APC</strong>
        </div>
      </div>
      {/* 품질 관리는 실제 검사 데이터를 다루므로 가상 표시를 붙이지 않는다. */}
      {pathname !== "/admin" && <span className="simulation-label">SIMULATION</span>}
      <nav aria-label="주요 메뉴">
        {(
          [
            { href: "/", label: "품질 검사", icon: "camera" },
            { href: "/admin", label: "품질 관리", icon: "document" },
            { href: "/market", label: "입찰 시장", icon: "market" },
            { href: "/control", label: "차량 관제", icon: "truck" },
          ] as const
        ).map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={pathname === item.href ? "active" : ""}
            aria-current={pathname === item.href ? "page" : undefined}
          >
            <Icon name={item.icon} />
            {item.label}
          </Link>
        ))}
      </nav>
      <div className="header-clock">
        <Icon name="clock" />
        <div>
          <small>
            {now
              ? now.toLocaleDateString("ko-KR", {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                  weekday: "short",
                })
              : "CQC 스마트 APC"}
          </small>
          <span>
            현재 시각{" "}
            <b>
              {now?.toLocaleTimeString("ko-KR", { hour12: false }) ??
                "--:--:--"}
            </b>
          </span>
        </div>
      </div>
    </header>
  );
}

export function Panel({
  title,
  icon,
  action,
  children,
  className = "",
}: {
  title: string;
  icon?: IconName;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <h2>
          {icon && <Icon name={icon} />} {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}
export function Stats({
  items,
}: {
  items: { label: string; value: ReactNode; icon: IconName; tone?: string }[];
}) {
  return (
    <section
      className="stats"
      style={{ "--stat-count": items.length } as React.CSSProperties}
      aria-label="운영 요약"
    >
      {items.map((item) => (
        <article className={`stat ${item.tone ?? ""}`} key={item.label}>
          <span className="stat-icon">
            <Icon name={item.icon} />
          </span>
          <div>
            <p>{item.label}</p>
            <strong>{item.value}</strong>
          </div>
        </article>
      ))}
    </section>
  );
}
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty-state">{children}</div>;
}
export function Progress({
  value,
  tone = "rose",
  label,
}: {
  value: number;
  tone?: string;
  label: string;
}) {
  return (
    <div
      className={`progress ${tone}`}
      role="progressbar"
      aria-label={label}
      aria-valuenow={Math.round(value)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <span style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}
