export const CSV_TIMEOUT_MS = 60_000;
const routes: [RegExp, string[]][] = [
  [/^snapshot$/, ["GET"]],
  [/^inspections(?:\.csv)?$/, ["GET"]],
  [/^statistics(?:\.csv)?$/, ["GET"]],
  [/^simulator$/, ["PUT"]],
  [/^fault-images$/, ["GET", "DELETE"]],
  [/^inspections\/(?!\.+\/)[A-Za-z0-9_.-]{1,64}\/review$/, ["PATCH"]],
  [/^previews\/[A-Za-z0-9_-]+$/, ["GET"]],
];
export async function proxyQuality(request: Request, path: string) {
  const headers = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
  };
  const error = (status: number, code: string) =>
    Response.json({ code }, { status, headers });
  const route = routes.find(([pattern]) => pattern.test(path));
  if (!route) return error(404, "NOT_FOUND");
  if (!route[1].includes(request.method))
    return error(405, "METHOD_NOT_ALLOWED");
  const incoming = new URL(request.url);
  // 컨테이너 안의 request.url은 내부 포트(3000)라 공개 주소(3100)와 다르다(#110).
  // 브라우저가 실제로 접속한 주소는 Host(프록시 경유면 X-Forwarded-Host)로 본다.
  const origin = request.headers.get("origin");
  const site = request.headers.get("sec-fetch-site");
  const host =
    request.headers.get("x-forwarded-host") ??
    request.headers.get("host") ??
    incoming.host;
  const sameOrigin = (value: string) => {
    try {
      return new URL(value).host === host;
    } catch {
      return false;
    }
  };
  if (
    request.method !== "GET" &&
    (site === "cross-site" ||
      (origin !== null && site !== "same-origin" && !sameOrigin(origin)))
  )
    return error(403, "CROSS_ORIGIN_WRITE");
  const base = process.env.CQC_QUALITY_BACKEND_URL;
  if (!base) return error(503, "BACKEND_UNCONFIGURED");
  try {
    const target = new URL(`/v1/quality/${path}`, base);
    if (!["http:", "https:"].includes(target.protocol))
      return error(503, "INVALID_BACKEND");
    target.search = incoming.search;
    const body = request.method === "GET" ? undefined : await request.text();
    if (body && body.length > 8192) return error(413, "BODY_TOO_LARGE");
    const response = await fetch(target, {
      method: request.method,
      body,
      headers: body ? { "Content-Type": "application/json" } : {},
      cache: "no-store",
      redirect: "error",
      // 대량 CSV는 Backend가 파일을 다 만든 뒤 응답한다(39,039건 약 14초, #109).
      signal: AbortSignal.any([
        request.signal,
        AbortSignal.timeout(path.endsWith(".csv") ? CSV_TIMEOUT_MS : 5000),
      ]),
    });
    if (!response.ok)
      return error(
        response.status,
        response.status === 409 ? "REVISION_CONFLICT" : "UPSTREAM_ERROR",
      );
    const contentType = response.headers.get("content-type") ?? "";
    const expected = path.startsWith("previews/")
      ? /^image\/(png|jpeg|webp)(;|$)/
      : path.endsWith(".csv")
        ? /^text\/csv(;|$)/
        : /^application\/json(;|$)/;
    if (!expected.test(contentType)) return error(502, "INVALID_CONTENT_TYPE");
    return new Response(response.body, {
      status: response.status,
      headers: {
        ...headers,
        "Content-Type": contentType,
        ...(path.endsWith(".csv")
          ? { "Content-Disposition": 'attachment; filename="cqc-quality.csv"' }
          : {}),
      },
    });
  } catch {
    return error(503, "BACKEND_UNAVAILABLE");
  }
}
