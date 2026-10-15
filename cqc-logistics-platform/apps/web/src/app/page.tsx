import QualityConsole from "@/components/QualityConsole";

export const dynamic = "force-dynamic";
export default function QualityPage() {
  return (
    <QualityConsole
      mode={process.env.CQC_QUALITY_MODE === "api" ? "api" : "demo"}
    />
  );
}
