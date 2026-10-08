import QualityAdmin from "@/components/QualityAdmin";

export const dynamic = "force-dynamic";
export default function QualityAdminPage() {
  return (
    <QualityAdmin
      mode={process.env.CQC_QUALITY_MODE === "api" ? "api" : "demo"}
    />
  );
}
