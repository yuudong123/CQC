import MarketView from "@/components/MarketView";

// 입찰 시장 관리자 화면(농가 판매 관리). 구매자 화면은 /market/buyer.
export default function MarketAdminPage() {
  return <MarketView role="admin" />;
}
