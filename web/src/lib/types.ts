export type Action =
  | { type: 'discard'; tiles?: number[]; tile?: number }
  | { type: 'riichi'; tiles?: number[]; tile?: number }
  | { type: 'tsumo' }
  | { type: 'ron' }
  | { type: 'pon'; tile: number }
  | { type: 'minkan'; tile: number }
  | { type: 'ankan'; tile: number }
  | { type: 'kakan'; tile: number }
  | { type: 'chi'; starts?: number[]; start?: number }
  | { type: 'pass' }

export interface MeldView {
  type: 'chi' | 'pon' | 'ankan' | 'minkan' | 'kakan'
  tiles: number[]
  from: number | null
}

export interface RiverTile {
  tile: number
  tsumogiri: boolean
  riichi: boolean
  claimed: boolean
}

export interface PlayerView {
  seat: number
  name: string
  isBot: boolean
  points: number
  riichi: boolean
  handCount: number
  melds: MeldView[]
  river: RiverTile[]
}

export interface WinnerView {
  winner: number
  yaku: { name: string; han: number }[]
  yakuman: { name: string; mult: number }[]
  han: number
  multiplier: number
  points: number
  hand: number[]
  melds: MeldView[]
}

export interface HandResult {
  type: 'win' | 'ron' | 'draw'
  winner?: number
  winners?: WinnerView[]
  from?: number | null
  tsumo?: boolean
  tile?: number
  yaku?: { name: string; han: number }[]
  yakuman?: { name: string; mult: number }[]
  han?: number
  multiplier?: number
  points?: number
  delta: Record<string, number>
  tenpai?: number[]
  hand?: number[]
  melds?: MeldView[]
  dora?: number[]
  ura?: number[]
}

export interface GameState {
  phase: 'waiting' | 'act' | 'claim' | 'hand_end' | 'game_end'
  dealer: number
  turn: number
  handNo: number
  totalHands: number
  honba: number
  riichiSticks: number
  wallLeft: number
  dora: number[]
  players: PlayerView[]
  result: HandResult | null
  you: {
    seat: number
    hand: number[]
    drawn: number | null
    waits: number[]
    furiten: boolean
    actions: Action[]
  }
}

export interface SeatInfo {
  index: number
  name: string
  isBot: boolean
  connected: boolean
}

export interface EmoteDef {
  id: string
  kind: 'text' | 'image'
  label: string
  text?: string
  url?: string
}

export interface LiveEmote {
  seat: number
  id: string
  at: number
  until: number
}

export interface RoomState {
  id: string
  name: string
  config: {
    mode: string
    singleTable: string
    maxPlayers: number
    minHan: number
    tsumoMode: string
    doraWrap: boolean
    startPoints: number
    actSeconds: number
    claimSeconds: number
    untimed: boolean
    emotesEnabled: boolean
  }
  emotes?: LiveEmote[]
  started: boolean
  hostSeat: number | null
  seats: SeatInfo[]
  chat: { seat: number; text: string; ts: number }[]
}
