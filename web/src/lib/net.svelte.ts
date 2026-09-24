import type { Action, GameState, RoomState } from './types'

const LS_KEY = 'banana.session'

interface Saved {
  roomId: string
  token: string
  name: string
}

function load(): Saved | null {
  try {
    return JSON.parse(localStorage.getItem(LS_KEY) ?? 'null')
  } catch {
    return null
  }
}

/** 單一 WebSocket 連線 + 全域遊戲狀態（Svelte 5 runes）。 */
class Net {
  ws: WebSocket | null = null
  seat = $state<number | null>(null)
  room = $state<RoomState | null>(null)
  game = $state<GameState | null>(null)
  log = $state<string[]>([])
  deadline = $state<number | null>(null)
  error = $state('')
  status = $state<'idle' | 'connecting' | 'open' | 'closed'>('idle')
  name = $state(load()?.name ?? '')
  roomId = $state('')

  readonly isHost = $derived(
    this.room != null && this.seat != null && this.room.hostSeat === this.seat,
  )
  readonly myActions = $derived(this.game?.you.actions ?? [])

  connect(roomId: string, name: string) {
    this.disconnect()
    this.roomId = roomId.toUpperCase()
    this.name = name
    const saved = load()
    const token = saved && saved.roomId === this.roomId ? saved.token : ''
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const qs = new URLSearchParams({ name })
    if (token) qs.set('token', token)
    const url = `${proto}://${location.host}/ws/${this.roomId}?${qs}`
    this.status = 'connecting'
    const ws = new WebSocket(url)
    this.ws = ws

    ws.onmessage = (ev) => this.#onMessage(JSON.parse(ev.data))
    ws.onopen = () => {
      this.status = 'open'
      this.error = ''
    }
    ws.onclose = () => {
      this.status = 'closed'
      // 自動重連：伺服器用 token 把你放回原座位
      if (this.roomId) setTimeout(() => this.#retry(), 1500)
    }
    ws.onerror = () => (this.error = '連線失敗')
  }

  #retry() {
    if (this.status === 'open' || !this.roomId) return
    this.connect(this.roomId, this.name)
  }

  #onMessage(msg: Record<string, unknown>) {
    switch (msg.t) {
      case 'hello': {
        this.seat = msg.seat as number
        this.room = msg.room as RoomState
        localStorage.setItem(
          LS_KEY,
          JSON.stringify({ roomId: this.roomId, token: msg.token, name: this.name } satisfies Saved),
        )
        break
      }
      case 'room':
        this.room = msg.room as RoomState
        break
      case 'state':
        this.room = msg.room as RoomState
        this.game = msg.state as GameState
        this.deadline = (msg.deadline as number | null) ?? null
        this.#pushEvents((msg.events as Record<string, unknown>[]) ?? [])
        break
      case 'error':
        this.error = msg.msg as string
        break
    }
  }

  #pushEvents(events: Record<string, unknown>[]) {
    if (!events.length) return
    const names = this.room?.seats ?? []
    const who = (s: unknown) => names[s as number]?.name ?? `座位${s}`
    const L = (t: unknown) => String.fromCharCode(65 + (t as number))
    const lines: string[] = []
    for (const e of events) {
      switch (e.t) {
        case 'hand_start':
          lines.push(`── 第 ${(e.hand_no as number) + 1} 局（莊家 ${who(e.dealer)}）──`)
          break
        case 'dora':
          lines.push(`翻寶牌指示牌：${L(e.tile)}`)
          break
        case 'discard':
          lines.push(`${who(e.seat)} 打出 ${L(e.tile)}`)
          break
        case 'meld':
          lines.push(`${who(e.seat)} ${meldLabel(e.kind as string)}`)
          break
        case 'riichi':
          lines.push(`${who(e.seat)} 宣告${e.double ? '兩' : ''}立直`)
          break
        case 'hand_end':
          lines.push(e.type === 'draw' ? '流局' : '和牌')
          break
      }
    }
    this.log = [...this.log, ...lines].slice(-120)
  }

  send(msg: Record<string, unknown>) {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(msg))
  }

  act(action: Action) {
    this.send({ t: 'action', action })
  }

  disconnect() {
    const ws = this.ws
    this.ws = null
    if (ws) {
      ws.onclose = null
      ws.close()
    }
  }

  leave() {
    this.roomId = ''
    this.disconnect()
    this.game = null
    this.room = null
    this.seat = null
    this.log = []
    localStorage.removeItem(LS_KEY)
  }
}

function meldLabel(kind: string) {
  return { chi: '吃', pon: '碰', ankan: '暗槓', minkan: '大明槓', kakan: '加槓' }[kind] ?? kind
}

export const net = new Net()
export const savedSession = load
