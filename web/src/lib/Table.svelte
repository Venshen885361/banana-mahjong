<script lang="ts">
  import { net } from './net.svelte'
  import Tile from './Tile.svelte'
  import Opponent from './Opponent.svelte'
  import Result from './Result.svelte'
  import EmoteBar from './EmoteBar.svelte'
  import EmoteBubble from './EmoteBubble.svelte'
  import TimingPanel from './TimingPanel.svelte'
  import { ACTION_LABEL, doraTiles, L, seatOrder } from './rules'
  import type { Action } from './types'

  const g = $derived(net.game!)
  const me = $derived(g.you)
  const dora = $derived(doraTiles(g.dora, net.room?.config.doraWrap ?? true))
  const others = $derived(seatOrder(me.seat, g.players.length).map((s) => g.players[s]))
  const myPlayer = $derived(g.players[me.seat])

  const act = $derived(Object.fromEntries(g.you.actions.map((a) => [a.type, a])) as Record<string, Action>)
  const ankanOptions = $derived(g.you.actions.filter((a) => a.type === 'ankan') as Extract<Action, { type: 'ankan' }>[])
  const kakanOptions = $derived(g.you.actions.filter((a) => a.type === 'kakan') as Extract<Action, { type: 'kakan' }>[])

  let riichiMode = $state(false)
  $effect(() => {
    if (!act.riichi) riichiMode = false
  })

  const discardable = $derived((act.discard as { tiles?: number[] })?.tiles ?? [])
  const riichiTiles = $derived((act.riichi as { tiles?: number[] })?.tiles ?? [])
  const selectable = $derived(riichiMode ? riichiTiles : discardable)

  // 手牌排序：抽到的牌單獨放右邊
  const handSorted = $derived.by(() => {
    const h = [...me.hand]
    if (me.drawn != null) {
      const i = h.lastIndexOf(me.drawn)
      if (i >= 0) h.splice(i, 1)
    }
    return h.sort((a, b) => a - b)
  })

  let now = $state(Date.now() / 1000)
  $effect(() => {
    const id = setInterval(() => (now = Date.now() / 1000), 250)
    return () => clearInterval(id)
  })
  const secsLeft = $derived(net.deadline ? Math.max(0, Math.ceil(net.deadline - now)) : null)

  function clickTile(t: number) {
    if (!selectable.includes(t)) return
    net.act(riichiMode ? { type: 'riichi', tile: t } : { type: 'discard', tile: t })
    riichiMode = false
  }

  function chi(start: number) {
    net.act({ type: 'chi', start })
  }

  let showLog = $state(false)
  let showTiming = $state(false)
  const myEmote = $derived(net.liveEmotes[me.seat])
</script>

<div class="min-h-full flex flex-col gap-2 p-2 sm:p-3 max-w-6xl mx-auto w-full">
  <!-- 頂部資訊列 -->
  <header class="flex items-center gap-3 text-sm bg-black/30 rounded-xl px-3 py-2 border border-white/10">
    <span class="font-bold">第 {g.handNo + 1}/{g.totalHands} 局</span>
    {#if g.honba}<span class="op-70">{g.honba} 本場</span>{/if}
    <span class="op-70">牌山 {g.wallLeft}</span>
    <div class="flex items-center gap-1">
      <span class="op-60 text-xs">寶牌</span>
      {#each g.dora as d (d)}
        <Tile size="xs" tile={d} dora />
      {/each}
    </div>
    {#if g.riichiSticks}<span class="text-banana text-xs">立直棒 ×{g.riichiSticks}</span>{/if}
    {#if net.room?.config.untimed}
      <span class="ml-auto text-xs op-50">不限時</span>
    {:else if secsLeft !== null && (g.phase === 'act' || g.phase === 'claim')}
      <span class="ml-auto tabular-nums {secsLeft <= 5 ? 'text-red-400' : 'op-70'}">{secsLeft}s</span>
    {:else}
      <span class="ml-auto"></span>
    {/if}
    {#if net.isHost}
      <button class="btn-ghost text-xs py-1" onclick={() => (showTiming = true)}>設定</button>
    {/if}
    <button class="btn-ghost text-xs py-1" onclick={() => (showLog = !showLog)}>紀錄</button>
    <button class="btn-ghost text-xs py-1" onclick={() => net.leave()}>離開</button>
  </header>

  <!-- 對手 -->
  <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
    {#each others as p (p.seat)}
      <Opponent {p} isDealer={p.seat === g.dealer} isTurn={p.seat === g.turn} {dora} />
    {/each}
  </div>

  {#if showLog}
    <div class="card max-h-40 overflow-auto text-xs font-mono grid gap-0.5">
      {#each net.log.slice(-60) as line, i (i)}<div class="op-80">{line}</div>{/each}
    </div>
  {/if}

  <!-- 我的牌河 -->
  <div class="rounded-xl bg-black/25 border border-white/10 p-2 min-h-12">
    <div class="text-xs op-50 mb-1">我的牌河</div>
    <div class="flex flex-wrap gap-0.5">
      {#each myPlayer.river as d, i (i)}
        <Tile size="sm" tile={d.tile} dim={d.claimed} dora={dora.includes(d.tile)} rotated={d.riichi} />
      {/each}
    </div>
  </div>

  <!-- 牌桌中央 -->
  <div class="flex-1 grid place-items-center py-4">
    <div class="grid place-items-center gap-3 rounded-2xl border border-white/10 bg-black/20 px-10 py-6">
      <div class="text-5xl font-black tabular-nums leading-none">{g.wallLeft}</div>
      <div class="text-xs op-50 tracking-widest">剩餘牌數</div>
      <div class="flex items-center gap-1 mt-1">
        {#each g.dora as d (d)}
          <Tile size="sm" tile={d} dora />
        {/each}
      </div>
      <div class="text-xs op-50">寶牌指示牌</div>
      <div class="text-sm op-70 mt-1">
        {#if g.phase === 'claim'}
          等待鳴牌回應…
        {:else if g.turn === me.seat}
          <span class="text-banana font-bold">輪到你了</span>
        {:else}
          {g.players[g.turn]?.name} 思考中…
        {/if}
      </div>
    </div>
  </div>

  <!-- 動作列 -->
  <div class="flex flex-wrap gap-2 items-center min-h-12">
    {#if act.tsumo}
      <button class="btn bg-banana text-black text-lg px-6" onclick={() => net.act({ type: 'tsumo' })}>自摸</button>
    {/if}
    {#if act.ron}
      <button class="btn bg-red-500 text-white text-lg px-6" onclick={() => net.act({ type: 'ron' })}>榮和</button>
    {/if}
    {#if act.riichi}
      <button class="btn {riichiMode ? 'bg-banana text-black' : 'bg-white/15 text-white'}" onclick={() => (riichiMode = !riichiMode)}>
        立直{riichiMode ? '（選一張打出）' : ''}
      </button>
    {/if}
    {#if act.pon}
      <button class="btn-ghost" onclick={() => net.act({ type: 'pon', tile: (act.pon as any).tile })}>
        碰 {L((act.pon as any).tile)}
      </button>
    {/if}
    {#if act.minkan}
      <button class="btn-ghost" onclick={() => net.act({ type: 'minkan', tile: (act.minkan as any).tile })}>
        槓 {L((act.minkan as any).tile)}
      </button>
    {/if}
    {#each ankanOptions as a (a.tile)}
      <button class="btn-ghost" onclick={() => net.act(a)}>暗槓 {L(a.tile)}</button>
    {/each}
    {#each kakanOptions as a (a.tile)}
      <button class="btn-ghost" onclick={() => net.act(a)}>加槓 {L(a.tile)}</button>
    {/each}
    {#if act.chi}
      {#each ((act.chi as any).starts ?? []) as s (s)}
        <button class="btn-ghost" onclick={() => chi(s)}>吃 {L(s)}{L(s + 1)}{L(s + 2)}</button>
      {/each}
    {/if}
    {#if act.pass}
      <button class="btn-ghost" onclick={() => net.act({ type: 'pass' })}>過</button>
    {/if}

    <EmoteBar />

    <div class="ml-auto flex items-center gap-3 text-xs">
      {#if me.furiten}<span class="text-red-400 font-bold">振聽</span>{/if}
      {#if me.waits.length}
        <span class="op-70">聽：{me.waits.map(L).join(' ')}</span>
      {/if}
      <span class="op-60">{ACTION_LABEL.discard}：點手牌</span>
    </div>
  </div>

  <!-- 我的手牌 -->
  <div
    class="relative rounded-xl border p-2 sm:p-3 transition
           {g.turn === me.seat && g.phase === 'act' ? 'border-banana/70 bg-banana/5' : 'border-white/10 bg-black/25'}"
  >
    {#if myEmote}
      <EmoteBubble emote={myEmote.emote} key={myEmote.key} />
    {/if}

    <div class="flex items-center gap-2 text-sm mb-2">
      {#if g.dealer === me.seat}<span class="px-1.5 rounded bg-red-600 text-white text-xs font-bold">莊</span>{/if}
      <span class="font-semibold">{myPlayer.name}</span>
      {#if myPlayer.riichi}<span class="text-xs text-banana font-bold">立直</span>{/if}
      <span class="ml-auto tabular-nums">{myPlayer.points.toLocaleString()}</span>
    </div>

    <div class="flex items-end gap-0.5 flex-wrap">
      {#each handSorted as t, i (`${t}-${i}`)}
        <Tile
          tile={t}
          dora={dora.includes(t)}
          clickable={selectable.includes(t)}
          dim={selectable.length > 0 && !selectable.includes(t)}
          onclick={() => clickTile(t)}
        />
      {/each}
      {#if me.drawn != null}
        <Tile
          tile={me.drawn}
          drawn
          dora={dora.includes(me.drawn)}
          clickable={selectable.includes(me.drawn)}
          dim={selectable.length > 0 && !selectable.includes(me.drawn)}
          onclick={() => clickTile(me.drawn!)}
        />
      {/if}

      {#each myPlayer.melds as m, mi (mi)}
        <span class="inline-flex gap-0.5 ml-2">
          {#each m.tiles as t, ti (ti)}
            <Tile size="sm" tile={t} back={m.type === 'ankan' && (ti === 0 || ti === 3)} called={m.type !== 'ankan' && ti === 0} />
          {/each}
        </span>
      {/each}
    </div>
  </div>
</div>

{#if showTiming}
  <TimingPanel onclose={() => (showTiming = false)} />
{/if}

{#if g.result && (g.phase === 'hand_end' || g.phase === 'game_end')}
  <Result result={g.result} players={g.players} isHost={net.isHost} gameOver={g.phase === 'game_end'} />
{/if}
