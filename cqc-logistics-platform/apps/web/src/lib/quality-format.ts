// Backend는 신뢰도를 확률×100 부동소수점으로 보내므로(예: 66.10390000000001) 화면에서는 소수 첫째 자리로 맞춘다.
export const formatPercent = (value: number | null) =>
  value === null ? "—" : `${value.toFixed(1)}%`;

export const formatMs = (value: number | null) =>
  value === null ? "—" : `${value.toFixed(1)}ms`;
