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
  if (
    request.method !== "GET" &&
    ((request.headers.get("origin") &&
      request.headers.get("origin") !== incoming.origin) ||
      request.headers.get("sec-fetch-site") === "cross-site")
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
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(5000)]),
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
