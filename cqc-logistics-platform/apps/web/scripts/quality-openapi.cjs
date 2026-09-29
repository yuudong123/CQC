/* eslint-disable @typescript-eslint/no-require-imports -- Generate the shared HTTP contract. */
const fs = require("node:fs");
const path = require("node:path");
const num = { type: "number", minimum: 0 },
  integer = { type: "integer", minimum: 0 },
  text = { type: "string" },
  bool = { type: "boolean" };
const nullable = (schema) => ({ ...schema, type: [schema.type, "null"] });
const enumeration = (values) => ({ type: "string", enum: values });
const object = (properties, required = Object.keys(properties)) => ({
  type: "object",
  properties,
  required,
  additionalProperties: false,
});
const array = (items, maxItems) => ({
  type: "array",
  items,
  ...(maxItems === undefined ? {} : { maxItems }),
});
const ref = (name) => ({ $ref: `#/components/schemas/${name}` });
const counts = { type: "object", additionalProperties: num };
const marker = enumeration([
  "NONE",
  "CULTIVAR_SUSPECT",
  "QUALITY_SUSPECT",
  "OTHER",
]);
const fault = enumeration([
  "INFERENCE_TIMEOUT",
  "INFERENCE_ERROR",
  "DB_ERROR",
  "CONTROL_REJECTED",
  "CONTROL_NO_RESPONSE",
  "CONTROL_FAILED",
]);
const id = {
  type: "string",
  pattern: "^[A-Za-z0-9_-]+$",
  minLength: 1,
  maxLength: 64,
};
const previewUrl = {
  type: "string",
  pattern: "^/api/quality/previews/[A-Za-z0-9_-]+$",
};
const percent = { type: "number", minimum: 0, maximum: 100 };
const resultProperties = {
  id,
  date: { type: "string", format: "date" },
  time: text,
  timestamp: num,
  variety: { type: ["string", "null"], enum: ["부사", "양광", null] },
  grade: { type: ["string", "null"], enum: ["특", "상", "보통", null] },
  confidence: nullable(percent),
  cultivarConfidence: nullable(percent),
  status: enumeration(["PASS", "REVIEW", "FAIL"]),
  processingStatus: enumeration([
    "COMPLETED",
    "INFERENCING",
    "TIMEOUT",
    "ERROR",
  ]),
  errorCode: enumeration(["NONE", ...fault.enum]),
  misclassification: marker,
  bin: text,
  virtualBrix: { type: ["number", "null"], minimum: 9, maximum: 18 },
  brixMeasured: { const: false },
  imageIndex: nullable(integer),
  inferenceMs: nullable(num),
  modelVersion: nullable(text),
  reviewRequired: bool,
  previewUrl,
  excluded: bool,
  control: enumeration(["NOT_REQUESTED", "SUCCEEDED", "FALLBACK", "NO_RESPONSE", "REJECTED", "FAILED"]),
  persistence: enumeration(["SAVED", "FAILED"]),
  faults: array(fault, 5),
};
const today = object({
  date: text,
  total: integer,
  normal: integer,
  review: integer,
  excluded: integer,
  grades: counts,
  varieties: counts,
  bins: counts,
  reinspection: integer,
  inferenceTotalMs: num,
  inferenceCount: integer,
  suspicions: object({
    CULTIVAR_SUSPECT: integer,
    QUALITY_SUSPECT: integer,
    OTHER: integer,
  }),
});
const runtimeProperties = {
  throughput: num,
  running: bool,
  concurrency: { type: "integer", minimum: 1, maximum: 64 },
  sequence: integer,
  tick: integer,
  faults: array(fault, 5),
  scope: enumeration(["ALL", "NEXT"]),
  jobs: array(ref("Job"), 64),
  history: array(ref("Result"), 200),
  images: array(ref("Result"), 100),
  points: array(ref("Point"), 1800),
  errors: array(ref("Result"), 50),
  today,
  lastSaved: nullable(num),
  dbDown: bool,
};
const runtime = object(
  runtimeProperties,
  Object.keys(runtimeProperties).filter(
    (key) => !["concurrency", "sequence", "tick", "scope"].includes(key),
  ),
);
const schemas = {
  Result: object(
    resultProperties,
    Object.keys(resultProperties).filter((k) => k !== "previewUrl"),
  ),
  Job: object(
    {
      id,
      index: integer,
      started: num,
      finish: num,
      faults: array(fault, 5),
      previewUrl,
    },
    ["id", "index", "started", "finish", "faults"],
  ),
  Point: object({
    at: num,
    count: integer,
    review: integer,
    excluded: integer,
  }),
  Component: object({
    status: enumeration(["healthy", "stopped", "error", "unknown"]),
    lastSeenAt: nullable(num),
    detail: text,
  }),
  Snapshot: object({
    contractVersion: { const: "1" },
    source: enumeration(["reference", "backend"]),
    capturedAt: num,
    revision: integer,
    capabilities: object({
      control: bool,
      faults: bool,
      review: bool,
      deleteImages: bool,
      concurrency: array({ type: "integer", minimum: 1, maximum: 64 }, 64),
    }),
    components: object(
      Object.fromEntries(
        ["Simulator", "Inference", "Backend", "MySQL"].map((key) => [
          key,
          ref("Component"),
        ]),
      ),
    ),
    retention: object({ history: integer, images: integer }, ["images"]),
    periodTotals: object(
      Object.fromEntries(["1", "5", "10", "30"].map((key) => [key, integer])),
    ),
    state: runtime,
  }),
  HistoryPage: object({
    items: array(ref("Result"), 200),
    total: integer,
    page: { type: "integer", minimum: 1 },
    pageSize: { type: "integer", enum: [50, 100, 200] },
    snapshotAt: num,
    bins: array(text),
  }),
  Summary: object({
    total: integer,
    normal: integer,
    excluded: integer,
    reinspection: integer,
    inferenceTotalMs: num,
    inferenceCount: integer,
    varieties: counts,
    grades: counts,
    bins: counts,
    suspicions: counts,
  }),
  Settings: object(
    {
      expectedRevision: integer,
      running: bool,
      concurrency: { type: "integer", minimum: 1, maximum: 64 },
      scope: enumeration(["ALL", "NEXT"]),
      faults: { ...array(fault, 5), uniqueItems: true },
    },
    ["expectedRevision"],
  ),
  Review: object({ misclassification: marker }),
  ReviewAck: object({ inspectionId: id, misclassification: marker }),
  ImageDelete: object({ ids: { ...array(id, 100), description: "Individual fault image IDs." } }),
  ImageDeleteAck: object({ deletedIds: { ...array(id, 100), description: "Deleted individual fault image IDs." } }),
  FaultImage: object({
    id,
    inspectionId: id,
    imageIndex: { type: "integer", minimum: 0, maximum: 11 },
    createdAt: num,
    errorCode: enumeration([
      "INFERENCE_TIMEOUT",
      "INFERENCE_ERROR",
      "INFERENCE_CONNECTION_ERROR",
      "INFERENCE_HTTP_ERROR",
      "INFERENCE_INVALID_RESPONSE",
    ]),
    previewUrl,
  }),
  FaultImages: object({ items: array(ref("FaultImage"), 100) }),
  Error: object({ code: text }),
};
const response = (schema) => ({
  description: "Success",
  content: { "application/json": { schema } },
});
const responses = (schema) => ({
  200: response(schema),
  404: response(ref("Error")),
  409: response(ref("Error")),
  410: response(ref("Error")),
  422: response(ref("Error")),
  503: response(ref("Error")),
});
const body = (schema) => ({
  required: true,
  content: { "application/json": { schema } },
});
const filterParameters = [
  ["from", { type: "string", format: "date" }],
  ["to", { type: "string", format: "date" }],
  ["variety", enumeration(["ALL", "부사", "양광"])],
  ["grade", enumeration(["ALL", "특", "상", "보통"])],
  ["bin", text],
  [
    "processingStatus",
    enumeration(["ALL", "COMPLETED", "INFERENCING", "TIMEOUT", "ERROR"]),
  ],
  ["errorCode", enumeration(["ALL", "NONE", ...fault.enum])],
  ["misclassification", enumeration(["ALL", ...marker.enum])],
  ["page", { type: "integer", minimum: 1, default: 1 }],
  ["pageSize", { type: "integer", enum: [50, 100, 200], default: 50 }],
  ["snapshotAt", num],
].map(([name, schema]) => ({ name, in: "query", required: false, schema }));
const csvResponses = {
  200: {
    description: "UTF-8 BOM CSV, all retained matching rows; no image fields.",
    content: { "text/csv": { schema: text } },
  },
  422: response(ref("Error")),
  503: response(ref("Error")),
};
const idParameter = { name: "id", in: "path", required: true, schema: id };
const document = {
  openapi: "3.1.0",
  info: {
    title: "CQC Quality Operations API",
    version: "1.0.0",
    description:
      "FE-first operations read model. Reference implementation uses memory and synthetic results. Existing POST /v1/inspections is unchanged. All responses use Cache-Control: no-store. Numeric timestamps are Unix milliseconds; calendar dates use Asia/Seoul.",
  },
  servers: [
    {
      url: "http://127.0.0.1:8101/v1/quality",
      description: "Local reference server",
    },
  ],
  paths: {
    "/snapshot": {
      get: {
        operationId: "qualitySnapshot",
        responses: responses(ref("Snapshot")),
      },
    },
    "/inspections": {
      get: {
        operationId: "qualityHistory",
        parameters: filterParameters,
        responses: responses(ref("HistoryPage")),
      },
    },
    "/inspections.csv": {
      get: {
        operationId: "qualityHistoryCsv",
        parameters: filterParameters,
        responses: csvResponses,
      },
    },
    "/statistics": {
      get: {
        operationId: "qualityStatistics",
        parameters: filterParameters,
        responses: responses(ref("Summary")),
      },
    },
    "/statistics.csv": {
      get: {
        operationId: "qualityStatisticsCsv",
        parameters: [
          ...filterParameters,
          {
            name: "minutes",
            in: "query",
            schema: { type: "integer", enum: [1, 5, 10, 30], default: 1 },
          },
        ],
        responses: csvResponses,
      },
    },
    "/simulator": {
      put: {
        operationId: "qualitySimulatorSettings",
        requestBody: body(ref("Settings")),
        responses: responses(ref("Snapshot")),
      },
    },
    "/inspections/{id}/review": {
      patch: {
        operationId: "qualityReview",
        parameters: [idParameter],
        requestBody: body(ref("Review")),
        responses: responses(ref("ReviewAck")),
      },
    },
    "/fault-images": {
      get: {
        operationId: "qualityFaultImages",
        responses: responses(ref("FaultImages")),
      },
      delete: {
        operationId: "qualityDeleteImages",
        requestBody: body(ref("ImageDelete")),
        responses: responses(ref("ImageDeleteAck")),
      },
    },
    "/previews/{id}": {
      get: {
        operationId: "qualityPreview",
        parameters: [{ ...idParameter, description: "Individual fault image ID for retained fault previews." }],
        responses: {
          200: {
            description: "Temporary or retained fault image. Never cache.",
            content: Object.fromEntries(
              ["image/png", "image/jpeg"].map((t) => [
                t,
                { schema: { type: "string", format: "binary" } },
              ]),
            ),
          },
          410: response(ref("Error")),
          503: response(ref("Error")),
        },
      },
    },
  },
  components: { schemas },
};
module.exports = document;
if (require.main === module) {
  const output = path.resolve(
    __dirname,
    "../../../../docs/contracts/quality-operations.openapi.json",
  );
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, JSON.stringify(document, null, 2) + "\n");
  console.log(output);
}
