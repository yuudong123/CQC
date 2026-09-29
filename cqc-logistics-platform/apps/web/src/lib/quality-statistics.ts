import type { Result } from "./quality-runtime";
export function summarizeInspections(records: Result[]) {
  const result = {
    total: records.length,
    normal: 0,
    excluded: 0,
    reinspection: 0,
    inferenceTotalMs: 0,
    inferenceCount: 0,
    varieties: {} as Record<string, number>,
    grades: {} as Record<string, number>,
    bins: {} as Record<string, number>,
    suspicions: { CULTIVAR_SUSPECT: 0, QUALITY_SUSPECT: 0, OTHER: 0 },
  };
  for (const row of records) {
    if (row.excluded) result.excluded++;
    else {
      result.normal++;
      if (row.variety)
        result.varieties[row.variety] =
          (result.varieties[row.variety] ?? 0) + 1;
      if (row.grade)
        result.grades[row.grade] = (result.grades[row.grade] ?? 0) + 1;
    }
    if (row.reviewRequired) result.reinspection++;
    if (row.inferenceMs !== null) {
      result.inferenceCount++;
      result.inferenceTotalMs += row.inferenceMs;
    }
    if (row.control === "SUCCEEDED" || row.control === "FALLBACK")
      result.bins[row.bin] = (result.bins[row.bin] ?? 0) + 1;
    if (row.misclassification !== "NONE")
      result.suspicions[row.misclassification]++;
  }
  return result;
}
export type InspectionSummary = ReturnType<typeof summarizeInspections>;
