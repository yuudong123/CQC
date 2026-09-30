/* eslint-disable @typescript-eslint/no-require-imports -- Node test TypeScript loader. */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const ts = require("typescript");
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, filename);
const { formatPercent, formatMs } = require("../src/lib/quality-format.ts");

test("Backend 부동소수점 신뢰도와 추론 시간을 소수 첫째 자리로 표시한다", () => {
  assert.equal(formatPercent(66.10390000000001), "66.1%");
  assert.equal(formatPercent(99.85579999999999), "99.9%");
  assert.equal(formatPercent(100), "100.0%");
  assert.equal(formatPercent(null), "—");
  assert.equal(formatMs(57.881), "57.9ms");
  assert.equal(formatMs(null), "—");
});
