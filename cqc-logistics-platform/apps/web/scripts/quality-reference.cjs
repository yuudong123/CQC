/* eslint-disable @typescript-eslint/no-require-imports -- Standalone contract reference server. */
const fs = require("node:fs");
const path = require("node:path");
const http = require("node:http");
const ts = require("typescript");
require.extensions[".ts"] = (module, filename) =>
  module._compile(
    ts.transpileModule(fs.readFileSync(filename, "utf8"), {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
      },
    }).outputText,
    filename,
  );
const { QualityReferenceService } = require("../src/lib/quality-reference.ts");
const service = new QualityReferenceService(Date.now, (index) =>
  fs.promises.readFile(
    path.join(__dirname, `../public/apples/apple-${index}-0.webp`),
  ),
);
const server = http.createServer(async (req, res) => {
  try {
    const chunks = [];
    let size = 0;
    for await (const chunk of req) {
      size += chunk.length;
      if (size > 8192) {
        res.writeHead(413).end();
        return;
      }
      chunks.push(chunk);
    }
    const response = await service.handle(
      new Request(`http://127.0.0.1${req.url}`, {
        method: req.method,
        headers: req.headers,
        ...(size ? { body: Buffer.concat(chunks) } : {}),
      }),
    );
    res.writeHead(response.status, Object.fromEntries(response.headers));
    res.end(Buffer.from(await response.arrayBuffer()));
  } catch {
    res
      .writeHead(500, { "Content-Type": "application/json" })
      .end('{"code":"REFERENCE_ERROR"}');
  }
});
const port = Number(process.env.CQC_REFERENCE_PORT || 8101);
server.listen(port, "127.0.0.1", () =>
  console.log(
    `CQC reference API: http://127.0.0.1:${port} (memory only; no real model/DB)`,
  ),
);
const timer = setInterval(() => service.tick(), 1000);
for (const signal of ["SIGINT", "SIGTERM"])
  process.on(signal, () => {
    clearInterval(timer);
    server.close();
  });
