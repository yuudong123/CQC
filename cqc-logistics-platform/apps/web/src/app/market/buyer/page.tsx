import MarketView from "@/components/MarketView";

// 입찰 시장 구매자 화면. 농가 메뉴 없이 출품 확인·입찰·낙찰 결제만 보여 준다.
export default function MarketBuyerPage() {
  return <MarketView role="buyer" />;
}
