import { proxyQuality } from "../../../../lib/quality-proxy";

type Context = { params: Promise<{ path: string[] }> };
async function handle(request: Request, context: Context) {
  return proxyQuality(request, (await context.params).path.join("/"));
}
export { handle as GET, handle as PUT, handle as PATCH, handle as DELETE };
