export const L = (t: number) => String.fromCharCode(65 + t)

/** 指示牌 -> 實際寶牌。Z 的下一張依房間設定環繞回 A。 */
export function doraTiles(indicators: number[], wrap = true): number[] {
  return indicators
    .map((i) => (i < 25 ? i + 1 : wrap ? 0 : -1))
    .filter((t) => t >= 0)
}

export const MELD_LABEL: Record<string, string> = {
  chi: '吃',
  pon: '碰',
  ankan: '暗槓',
  minkan: '大明槓',
  kakan: '加槓',
}

export const ACTION_LABEL: Record<string, string> = {
  tsumo: '自摸',
  ron: '榮和',
  riichi: '立直',
  chi: '吃',
  pon: '碰',
  minkan: '槓',
  ankan: '暗槓',
  kakan: '加槓',
  pass: '過',
  discard: '打牌',
}

export function seatOrder(mySeat: number, n: number): number[] {
  return Array.from({ length: n - 1 }, (_, i) => (mySeat + i + 1) % n)
}
