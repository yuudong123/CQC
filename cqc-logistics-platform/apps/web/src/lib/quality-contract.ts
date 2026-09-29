/** FE-01: the screen contract used by mock data and the future inspection API. */
export type InspectionStatus = "PASS" | "REVIEW" | "FAIL";
export type ProcessingStatus =
  "COMPLETED" | "INFERENCING" | "TIMEOUT" | "ERROR";
export type ErrorCode =
  | "NONE"
  | "INFERENCE_TIMEOUT"
  | "INFERENCE_ERROR"
  | "DB_ERROR"
  | "CONTROL_REJECTED"
  | "CONTROL_NO_RESPONSE";
export type MisclassificationType =
  "NONE" | "CULTIVAR_SUSPECT" | "QUALITY_SUSPECT" | "OTHER";

export type InspectionRecord = {
  id: string;
  date: string;
  time: string;
  variety: "부사" | "양광" | null;
  grade: "특" | "상" | "보통" | null;
  confidence: number | null;
  status: InspectionStatus;
  processingStatus: ProcessingStatus;
  errorCode: ErrorCode;
  misclassification: MisclassificationType;
  bin: string;
  virtualBrix: number | null;
  brixMeasured: false;
  imageIndex: number;
};

export type QualityFilterState = {
  from: string;
  to: string;
  variety: "ALL" | NonNullable<InspectionRecord["variety"]>;
  grade: "ALL" | NonNullable<InspectionRecord["grade"]>;
  bin: "ALL" | string;
  processingStatus: "ALL" | ProcessingStatus;
  errorCode: "ALL" | ErrorCode;
  misclassification: "ALL" | MisclassificationType;
  pageSize: 50 | 100 | 200;
};

export const PAGE_SIZES = [50, 100, 200] as const;
export const DEFAULT_QUALITY_FILTERS: QualityFilterState = {
  from: "",
  to: "",
  variety: "ALL",
  grade: "ALL",
  bin: "ALL",
  processingStatus: "ALL",
  errorCode: "ALL",
  misclassification: "ALL",
  pageSize: 50,
};

export const PROCESSING_STATUS_LABEL: Record<ProcessingStatus, string> = {
  COMPLETED: "처리 완료",
  INFERENCING: "추론 중",
  TIMEOUT: "시간 초과",
  ERROR: "시스템 오류",
};
export const ERROR_LABEL: Record<ErrorCode, string> = {
  NONE: "오류 없음",
  INFERENCE_TIMEOUT: "추론 시간 초과",
  INFERENCE_ERROR: "추론 오류",
  DB_ERROR: "DB 저장 오류",
  CONTROL_REJECTED: "제어 거부",
  CONTROL_NO_RESPONSE: "제어 무응답",
};
export const MISCLASSIFICATION_LABEL: Record<MisclassificationType, string> = {
  NONE: "오판 의심 없음",
  CULTIVAR_SUSPECT: "품종 의심",
  QUALITY_SUSPECT: "품질 의심",
  OTHER: "기타",
};

export const MOCK_INSPECTIONS: InspectionRecord[] = [
  [
    "SAMPLE-0012",
    "2026-09-28",
    "14:32:12",
    "양광",
    "특",
    94.2,
    "PASS",
    "COMPLETED",
    "NONE",
    "NONE",
    "DEMO_BIN_07",
    14.1,
    0,
  ],
  [
    "SAMPLE-0011",
    "2026-09-28",
    "14:32:11",
    "부사",
    "상",
    91.1,
    "PASS",
    "COMPLETED",
    "NONE",
    "NONE",
    "DEMO_BIN_04",
    13.3,
    1,
  ],
  [
    "SAMPLE-0010",
    "2026-09-28",
    "14:32:10",
    "양광",
    "보통",
    86.5,
    "PASS",
    "COMPLETED",
    "NONE",
    "NONE",
    "DEMO_BIN_11",
    11.9,
    2,
  ],
  [
    "SAMPLE-0009",
    "2026-09-28",
    "14:32:09",
    "양광",
    "상",
    78.3,
    "REVIEW",
    "COMPLETED",
    "NONE",
    "NONE",
    "TEST_REINSPECTION_BIN",
    12.0,
    3,
  ],
  [
    "SAMPLE-0008",
    "2026-09-28",
    "14:32:08",
    "부사",
    "보통",
    62.1,
    "FAIL",
    "COMPLETED",
    "NONE",
    "QUALITY_SUSPECT",
    "TEST_REINSPECTION_BIN",
    15.2,
    4,
  ],
  [
    "SAMPLE-0007",
    "2026-09-28",
    "14:32:07",
    "부사",
    "특",
    92.7,
    "PASS",
    "COMPLETED",
    "NONE",
    "NONE",
    "DEMO_BIN_01",
    13.8,
    5,
  ],
  [
    "SAMPLE-0006",
    "2026-09-28",
    "14:32:06",
    "양광",
    "특",
    95.1,
    "PASS",
    "COMPLETED",
    "NONE",
    "NONE",
    "DEMO_BIN_07",
    14.1,
    0,
  ],
  [
    "SAMPLE-0005",
    "2026-09-28",
    "14:32:05",
    "부사",
    "상",
    86.6,
    "PASS",
    "COMPLETED",
    "NONE",
    "NONE",
    "DEMO_BIN_04",
    13.3,
    1,
  ],
  [
    "SAMPLE-0004",
    "2026-09-28",
    "14:32:04",
    "양광",
    "보통",
    90.3,
    "PASS",
    "COMPLETED",
    "NONE",
    "NONE",
    "DEMO_BIN_11",
    11.9,
    2,
  ],
  [
    "SAMPLE-0003",
    "2026-09-28",
    "14:32:03",
    "양광",
    "상",
    93.8,
    "PASS",
    "COMPLETED",
    "NONE",
    "NONE",
    "DEMO_BIN_10",
    12.0,
    3,
  ],
  [
    "SAMPLE-0002",
    "2026-09-28",
    "14:32:02",
    "부사",
    "보통",
    87.6,
    "REVIEW",
    "TIMEOUT",
    "INFERENCE_TIMEOUT",
    "NONE",
    "TEST_REINSPECTION_BIN",
    15.2,
    4,
  ],
  [
    "SAMPLE-0001",
    "2026-09-28",
    "14:32:01",
    "부사",
    "특",
    91.8,
    "FAIL",
    "ERROR",
    "INFERENCE_ERROR",
    "QUALITY_SUSPECT",
    "TEST_REINSPECTION_BIN",
    13.8,
    5,
  ],
].map(
  ([
    id,
    date,
    time,
    variety,
    grade,
    confidence,
    status,
    processingStatus,
    errorCode,
    misclassification,
    bin,
    virtualBrix,
    imageIndex,
  ]) =>
    ({
      id,
      date,
      time,
      variety,
      grade,
      confidence,
      status,
      processingStatus,
      errorCode,
      misclassification,
      bin,
      virtualBrix,
      brixMeasured: false,
      imageIndex,
    }) as InspectionRecord,
);
