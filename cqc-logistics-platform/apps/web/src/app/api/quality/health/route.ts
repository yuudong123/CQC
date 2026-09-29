/** Only proxy the existing CQC quality backend health endpoint, not logistics. */
export async function GET() {
  const base = process.env.CQC_QUALITY_BACKEND_URL;
  const headers = { "Cache-Control": "no-store" };
  if (!base) return Response.json({ status: "unconfigured" }, { headers });
  try {
    const response = await fetch(new URL("/health", base), {
      cache: "no-store",
      signal: AbortSignal.timeout(2500),
    });
    const payload = await response.json();
    if (!response.ok || payload.status !== "ok")
      throw new Error("Unhealthy backend");
    return Response.json({ status: "ok" }, { headers });
  } catch {
    return Response.json({ status: "unavailable" }, { status: 502, headers });
  }
}
