export const qualityBins = ["부사", "양광"].flatMap((variety, varietyIndex) =>
  ["특", "상", "보통"].flatMap((grade, gradeIndex) =>
    ["12° 미만", "12° 이상"].map((sweetness, sweetnessIndex) => ({
      code: `DEMO_BIN_${String(varietyIndex * 6 + gradeIndex * 2 + sweetnessIndex + 1).padStart(2, "0")}`,
      variety,
      grade,
      sweetness,
    })),
  ),
);
