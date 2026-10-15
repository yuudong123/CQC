/* eslint-disable @typescript-eslint/no-require-imports -- Node test-only TypeScript CommonJS loader. */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
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
const { GET } = require("../src/app/api/quality/health/route.ts");
test("health proxy: unconfigured, healthy, unhealthy and unreachable", async () => {
  const old = process.env.CQC_QUALITY_BACKEND_URL,
    originalFetch = global.fetch;
  try {
    delete process.env.CQC_QUALITY_BACKEND_URL;
    global.fetch = () => {
      throw new Error("Unexpected request");
    };
    let response = await GET();
    assert.equal((await response.json()).status, "unconfigured");
    assert.equal(response.headers.get("cache-control"), "no-store");
    process.env.CQC_QUALITY_BACKEND_URL = "http://backend:8000";
    global.fetch = async (url, options) => {
      assert.equal(String(url), "http://backend:8000/health");
      assert.equal(options.cache, "no-store");
      assert.ok(options.signal);
      return Response.json({ status: "ok" });
    };
    response = await GET();
    assert.equal(response.status, 200);
    assert.equal((await response.json()).status, "ok");
    global.fetch = async () => Response.json({ status: "failed" });
    response = await GET();
    assert.equal(response.status, 502);
    global.fetch = async () => {
      throw new Error("secret internal address");
    };
    response = await GET();
    assert.equal(response.status, 502);
    assert.equal((await response.json()).status, "unavailable");
  } finally {
    global.fetch = originalFetch;
    if (old === undefined) delete process.env.CQC_QUALITY_BACKEND_URL;
    else process.env.CQC_QUALITY_BACKEND_URL = old;
  }
});
